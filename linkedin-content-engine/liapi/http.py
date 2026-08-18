"""Minimal HTTP for the LinkedIn API.

Stdlib only, on purpose. The venv carries exactly one dependency (anthropic)
and this code has to keep working when that changes. Every call returns the
same shape so callers never have to care whether a request "failed": a 403 is
data, not an exception, because telling 403 apart from 401 is the whole point
of the endpoint probe.
"""
import json
import socket
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "hi-im-alex-content-engine/0.1"


# Two distinct non-HTTP outcomes, because conflating them is dangerous.
#   NOT_SENT   the request never reached LinkedIn. Retrying is safe.
#   AMBIGUOUS  the request went out and the reply was lost. LinkedIn may well
#              have created the post. Retrying could duplicate it.
STATUS_NOT_SENT = 0
STATUS_AMBIGUOUS = -1


class Response(object):
    def __init__(self, status, headers, body):
        self.status = status
        self.headers = headers
        self.body = body

    @property
    def ambiguous(self):
        return self.status == STATUS_AMBIGUOUS

    @property
    def ok(self):
        return 200 <= self.status < 300

    def json(self):
        """Parsed body, or None when the body is empty or not JSON.

        LinkedIn returns an empty body on some successes and an HTML error page
        on some failures, so this must never raise.
        """
        if not self.body:
            return None
        try:
            return json.loads(self.body)
        except ValueError:
            return None

    def header(self, name):
        """Case-insensitive header lookup. LinkedIn returns the post id in
        `x-restli-id`, and header casing across their tiers is not consistent."""
        target = name.lower()
        for key in self.headers:
            if key.lower() == target:
                return self.headers[key]
        return None

    def __repr__(self):
        return "<Response %s %s>" % (self.status, (self.body or "")[:200])


def request(method, url, headers=None, body=None, timeout=30):
    data = None
    headers = dict(headers or {})
    headers.setdefault("User-Agent", USER_AGENT)

    if body is not None:
        if isinstance(body, (dict, list)):
            data = json.dumps(body).encode("utf-8")
            headers.setdefault("Content-Type", "application/json")
        elif isinstance(body, bytes):
            data = body
        else:
            data = body.encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return Response(resp.status, dict(resp.headers), resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        # The error body carries LinkedIn's actual complaint. Keep it.
        return Response(exc.code, dict(exc.headers or {}), exc.read().decode("utf-8", "replace"))
    except urllib.error.URLError as exc:
        # urllib wraps URLError around the connect and send phase only, so
        # reaching here means the request did not get out. Safe to retry.
        return Response(STATUS_NOT_SENT, {}, "network error before sending: %s" % (exc.reason,))
    except socket.gaierror as exc:
        # Name resolution failed, so no connection was ever opened and nothing
        # was sent. Calling this ambiguous would send someone to check their
        # feed for a post that cannot exist.
        return Response(STATUS_NOT_SENT, {}, "could not resolve LinkedIn: %s" % (exc,))
    except (socket.timeout, TimeoutError) as exc:
        # A timeout that is NOT wrapped in URLError comes from reading the
        # reply, which means the request was already on the wire. LinkedIn may
        # have created the post. Never report this as "nothing went live".
        return Response(STATUS_AMBIGUOUS, {}, "timed out waiting for the reply: %s" % (exc,))
    except OSError as exc:
        # Anything else at the socket layer after the request was built. Treat
        # as ambiguous rather than assume, because assuming wrong here means a
        # duplicate post.
        return Response(STATUS_AMBIGUOUS, {}, "connection failed after sending: %s" % (exc,))


def get(url, headers=None, timeout=30):
    return request("GET", url, headers=headers, timeout=timeout)


def post(url, headers=None, body=None, timeout=30):
    return request("POST", url, headers=headers, body=body, timeout=timeout)


def form_post(url, fields, timeout=30):
    """application/x-www-form-urlencoded. The OAuth token endpoint requires it."""
    encoded = urllib.parse.urlencode(fields)
    return request(
        "POST", url,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        body=encoded, timeout=timeout,
    )
