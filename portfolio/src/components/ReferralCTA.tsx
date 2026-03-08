import { ExternalLink, MapPin, Zap, DollarSign } from 'lucide-react';
import { config } from '../config';

export function ReferralCTA() {
  const { referralUrl, personalKickback, monthlyPrice, freeWeekValue } = config.networkSchool;
  const effectiveFirstMonth = monthlyPrice - freeWeekValue - personalKickback;

  return (
    <section className="relative overflow-hidden bg-gradient-to-br from-blue-950/60 via-gray-900 to-gray-900 border border-blue-500/20 rounded-2xl p-8">
      {/* Glow */}
      <div className="absolute -top-24 -right-24 w-64 h-64 bg-blue-600/10 rounded-full blur-3xl" />

      <div className="relative">
        <div className="flex items-center gap-2 text-blue-400 text-sm font-semibold mb-4">
          <MapPin size={14} />
          Network School · Kuala Lumpur, Malaysia
        </div>

        <h2 className="text-2xl md:text-3xl font-bold text-white mb-3">
          Come build here with me
        </h2>
        <p className="text-gray-400 max-w-xl mb-8 leading-relaxed">
          Network School is a 12-month residential program for builders. $1,500/mo — housing, community, and co-working in KL.
          I'm making it even cheaper for the first person to use my code.
        </p>

        {/* Deal breakdown */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
          <div className="bg-gray-900/80 border border-gray-800 rounded-xl p-4">
            <div className="text-gray-500 text-xs mb-1">Normal price</div>
            <div className="text-white text-xl font-bold line-through decoration-gray-600">
              ${monthlyPrice.toLocaleString()}<span className="text-sm font-normal text-gray-500">/mo</span>
            </div>
          </div>

          <div className="bg-blue-950/60 border border-blue-500/30 rounded-xl p-4">
            <div className="text-blue-400 text-xs mb-1 font-medium">With my referral code</div>
            <div className="text-blue-300 font-semibold text-sm">− ${freeWeekValue} (1 week free)</div>
            <div className="text-blue-300 font-semibold text-sm">− ${personalKickback.toLocaleString()} Venmo from me</div>
          </div>

          <div className="bg-emerald-950/40 border border-emerald-500/30 rounded-xl p-4">
            <div className="text-emerald-400 text-xs mb-1 font-medium">Your first month</div>
            <div className="text-emerald-300 text-2xl font-bold">
              ${effectiveFirstMonth}<span className="text-sm font-normal text-emerald-400">/mo</span>
            </div>
            <div className="text-emerald-500 text-xs mt-0.5">Less than half price</div>
          </div>
        </div>

        {/* Fine print */}
        <div className="flex flex-wrap gap-x-6 gap-y-2 text-xs text-gray-500 mb-8">
          <span className="flex items-center gap-1.5">
            <Zap size={12} className="text-yellow-400" />
            1 week free applied at checkout via referral link
          </span>
          <span className="flex items-center gap-1.5">
            <DollarSign size={12} className="text-emerald-400" />
            $500 Venmo paid personally when you arrive
          </span>
        </div>

        <a
          href={referralUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-3 bg-blue-600 hover:bg-blue-500 text-white font-semibold px-8 py-4 rounded-xl transition-colors duration-200 shadow-lg shadow-blue-600/20"
        >
          Use my referral code
          <ExternalLink size={16} />
        </a>

        <p className="text-gray-600 text-xs mt-3">
          ns.com/acoffman/invite
        </p>
      </div>
    </section>
  );
}
