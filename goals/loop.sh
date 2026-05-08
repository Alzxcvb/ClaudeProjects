#!/bin/bash

# Ralph Loop — Goals
# Headless build loop. Runs Claude Code repeatedly with scoped permissions, rate limiting, and persistent logging.
# Usage: caffeinate bash loop.sh

set +e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLAN_FILE="$PROJECT_DIR/IMPLEMENTATION_PLAN.md"
RALPH_DIR="$PROJECT_DIR/.ralph"
LOG_FILE="$RALPH_DIR/run-$(date +%Y-%m-%d).log"

MAX_ITERATIONS=30
ITERATION=0
CONSECUTIVE_ERRORS=0
MAX_CONSECUTIVE_ERRORS=3
ERROR_COOLDOWN=60

# ETA tracking — computed from rolling avg of successful iterations
TOTAL_ELAPSED=0
SUCCESS_COUNT=0
RUN_START=$(date +%s)

# Rate limiting — prevents runaway token burn
MAX_CALLS_PER_HOUR=30
CALL_COUNT_FILE="$RALPH_DIR/.calls"
CALL_RESET_FILE="$RALPH_DIR/.calls_reset"

# Scoped tool permissions — Goals is Next.js + Prisma. Verification via `npx tsc --noEmit`.
# Broad git access so `cd ... && git X` patterns succeed (lesson from alex-workout run).
# Explicitly NOT permitted: npm install, npx prisma migrate, anything mutating deps or DB.
ALLOWED_TOOLS="Write,Read,Edit,MultiEdit,Glob,Grep,Bash(git *),Bash(npx tsc *),Bash(npx eslint *),Bash(grep *),Bash(ls *),Bash(cat *),Bash(tail *),Bash(head *),Bash(wc *),Bash(find *),Bash(echo *),Bash(node *),Bash(cd *),Bash(test *),Bash(true)"

mkdir -p "$RALPH_DIR"

log() {
    local msg="$1"
    echo "$msg" | tee -a "$LOG_FILE"
}

get_call_count() {
    local now
    now=$(date +%s)
    local reset_time=0

    if [ -f "$CALL_RESET_FILE" ]; then
        reset_time=$(cat "$CALL_RESET_FILE")
    fi

    if [ $((now - reset_time)) -ge 3600 ]; then
        echo "0" > "$CALL_COUNT_FILE"
        echo "$now" > "$CALL_RESET_FILE"
    fi

    if [ -f "$CALL_COUNT_FILE" ]; then
        cat "$CALL_COUNT_FILE"
    else
        echo "0"
    fi
}

increment_call_count() {
    local count
    count=$(get_call_count)
    echo $((count + 1)) > "$CALL_COUNT_FILE"
}

check_rate_limit() {
    local count
    count=$(get_call_count)
    if [ "$count" -ge "$MAX_CALLS_PER_HOUR" ]; then
        local reset_time now wait_secs
        reset_time=$(cat "$CALL_RESET_FILE")
        now=$(date +%s)
        wait_secs=$((3600 - (now - reset_time)))
        log "Rate limit reached ($count/$MAX_CALLS_PER_HOUR calls this hour). Waiting ${wait_secs}s for reset..."
        sleep "$wait_secs"
        get_call_count > /dev/null
    fi
}

log "Starting Ralph Loop: Goals"
log "  Project:    $PROJECT_DIR"
log "  Max iter:   $MAX_ITERATIONS"
log "  Rate limit: $MAX_CALLS_PER_HOUR calls/hour"
log "  Log:        $LOG_FILE"
log "  Started:    $(date '+%Y-%m-%d %H:%M:%S')"
log ""

while [ $ITERATION -lt $MAX_ITERATIONS ]; do
    ITERATION=$((ITERATION + 1))
    ITER_START=$(date +%s)

    log "================================================================"
    log "Iteration $ITERATION of $MAX_ITERATIONS  [$(date '+%H:%M:%S')]"
    log "================================================================"

    if [ -f "$PLAN_FILE" ]; then
        INCOMPLETE=$(grep -c "^- \[ \]" "$PLAN_FILE" 2>/dev/null | tr -cd '0-9' || echo "0")
        INCOMPLETE=${INCOMPLETE:-0}
        COMPLETE=$(grep -c "^- \[x\]" "$PLAN_FILE" 2>/dev/null | tr -cd '0-9' || echo "0")
        COMPLETE=${COMPLETE:-0}
        # Anchor to list-item lines so the literal word "BLOCKED:" in the
        # instructions header doesn't trip a false positive.
        BLOCKED=$(grep -cE "^- (\[[x ]\] )?BLOCKED:" "$PLAN_FILE" 2>/dev/null | tr -cd '0-9' || echo "0")
        BLOCKED=${BLOCKED:-0}

        log "Status: $COMPLETE complete, $INCOMPLETE remaining, $BLOCKED blocked"

        if [ "$SUCCESS_COUNT" -gt 0 ] && [ "$INCOMPLETE" -gt 0 ]; then
            AVG_ITER=$((TOTAL_ELAPSED / SUCCESS_COUNT))
            ETA_SECS=$((INCOMPLETE * AVG_ITER))
            ETA_MIN=$((ETA_SECS / 60))
            RUN_NOW=$(date +%s)
            ELAPSED_SO_FAR=$(((RUN_NOW - RUN_START) / 60))
            log "ETA: ~${ETA_MIN} min remaining (avg ${AVG_ITER}s/task, ${ELAPSED_SO_FAR} min elapsed, ${SUCCESS_COUNT} tasks done)"
        elif [ "$INCOMPLETE" -gt 0 ]; then
            log "ETA: pending — first iteration will calibrate"
        fi
        log ""

        if [ "$INCOMPLETE" -eq 0 ] 2>/dev/null; then
            log "All tasks complete!"
            log "  Total iterations: $ITERATION"
            log "  Tasks completed:  $COMPLETE"
            exit 0
        fi

        # Detect a true stall: INCOMPLETE failed to drop across two consecutive iterations.
        # This catches "all remaining are stuck" without the prior bug of comparing INCOMPLETE
        # to BLOCKED — those are disjoint counts (BLOCKED lines lose their `- [ ]` checkbox)
        # and equality between them was a numerical coincidence, not a stall signal.
        if [ "$ITERATION" -gt 1 ] && [ "$INCOMPLETE" -gt 0 ] && [ "$INCOMPLETE" -eq "$LAST_INCOMPLETE" ] && [ "$LAST_INCOMPLETE" -eq "$PREV_INCOMPLETE" ]; then
            log "No progress for 2 iterations ($INCOMPLETE remaining unchanged). Stopping for human review."
            grep -E "^- (\[[x ]\] )?BLOCKED:" "$PLAN_FILE" 2>/dev/null | tee -a "$LOG_FILE"
            exit 1
        fi
        PREV_INCOMPLETE=${LAST_INCOMPLETE:-$INCOMPLETE}
        LAST_INCOMPLETE=$INCOMPLETE
    fi

    check_rate_limit
    increment_call_count

    log "Running build mode..."
    cd "$PROJECT_DIR"

    TEMP_OUTPUT=$(mktemp)
    trap "rm -f $TEMP_OUTPUT" EXIT

    RETRY=0
    MAX_RETRIES=3
    EXIT_CODE=1
    while [ $RETRY -lt $MAX_RETRIES ]; do
        # Prompt piped via stdin so --allowedTools (variadic) doesn't eat it.
        echo "Read PROMPT_build.md and follow its instructions. Pick the next incomplete task from IMPLEMENTATION_PLAN.md, implement it, verify it works, commit, and mark it complete." | \
        claude -p --verbose --output-format stream-json \
            --allowedTools "$ALLOWED_TOOLS" 2>&1 | \
            while IFS= read -r line; do
                echo "$line" >> "$TEMP_OUTPUT"
                if echo "$line" | grep -q '"type":"tool_use"'; then
                    TOOL=$(echo "$line" | sed -n 's/.*"name":"\([^"]*\)".*/\1/p')
                    FILEPATH=$(echo "$line" | sed -n 's/.*"file_path":"\([^"]*\)".*/\1/p' | sed 's|.*/||')
                    CMD=$(echo "$line" | sed -n 's/.*"command":"\([^"]*\)".*/\1/p' | head -c 60)
                    if [ -n "$TOOL" ]; then
                        if [ -n "$FILEPATH" ]; then
                            log "  > $TOOL: $FILEPATH"
                        elif [ -n "$CMD" ]; then
                            log "  > $TOOL: $CMD..."
                        else
                            log "  > $TOOL"
                        fi
                    fi
                elif echo "$line" | grep -q '"type":"result"'; then
                    if echo "$line" | grep -q '"is_error":false'; then
                        log "  Task complete"
                    else
                        log "  Task failed"
                    fi
                fi
            done
        EXIT_CODE=${PIPESTATUS[0]}

        OUTPUT=$(cat "$TEMP_OUTPUT")

        if echo "$OUTPUT" | grep -q "No messages returned"; then
            log "Claude API error (No messages returned) — recoverable"
            EXIT_CODE=1
        fi

        if [ $EXIT_CODE -eq 0 ]; then
            CONSECUTIVE_ERRORS=0
            break
        fi

        RETRY=$((RETRY + 1))
        if [ $RETRY -lt $MAX_RETRIES ]; then
            log "Claude failed (exit $EXIT_CODE), retry $RETRY of $MAX_RETRIES in 10s..."
            sleep 10
        fi
    done

    ITER_END=$(date +%s)
    ITER_ELAPSED=$((ITER_END - ITER_START))

    if [ $EXIT_CODE -ne 0 ]; then
        CONSECUTIVE_ERRORS=$((CONSECUTIVE_ERRORS + 1))
        log "Failed in ${ITER_ELAPSED}s (consecutive errors: $CONSECUTIVE_ERRORS/$MAX_CONSECUTIVE_ERRORS)"

        if [ $CONSECUTIVE_ERRORS -ge $MAX_CONSECUTIVE_ERRORS ]; then
            log "Too many consecutive errors. Stopping for human review."
            exit 1
        fi

        log "Cooling down for ${ERROR_COOLDOWN}s..."
        sleep $ERROR_COOLDOWN
    else
        TOTAL_ELAPSED=$((TOTAL_ELAPSED + ITER_ELAPSED))
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        log "Done in ${ITER_ELAPSED}s. Sleeping 15s before next iteration..."
        sleep 15
    fi
done

log "Max iterations ($MAX_ITERATIONS) reached."
exit 1
