"""Enterprise dark theme CSS for LeadAgent.io."""

ENTERPRISE_CSS = """
<style>
    [data-testid="stAppViewContainer"] {
        background: radial-gradient(circle at 10% 20%, rgb(0, 0, 0) 0%, rgb(18, 18, 18) 100.2%);
        color: #e2e8f0;
        font-family: 'Inter', system-ui, sans-serif;
    }
    [data-testid="stSidebar"] {
        background-color: rgba(26, 32, 44, 0.5) !important;
        backdrop-filter: blur(12px);
        border-right: 1px solid rgba(255, 255, 255, 0.08);
    }
    .starfield {
        position: fixed; top: 0; left: 0; right: 0; bottom: 0;
        pointer-events: none; z-index: 0; opacity: 0.55;
    }
    .starfield::before {
        content: ""; position: absolute; top: -50%; left: -50%;
        width: 200%; height: 200%;
        background-image:
            radial-gradient(1px 1px at 20px 30px, #fff 100%, transparent 0),
            radial-gradient(1px 1px at 90px 120px, #93c5fd 100%, transparent 0);
        background-repeat: repeat; background-size: 380px 260px;
        animation: drift-stars 90s linear infinite;
    }
    @keyframes drift-stars {
        from { transform: translate(0, 0); }
        to { transform: translate(-380px, -260px); }
    }
    .premium-header {
        position: relative; overflow: hidden;
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(8px);
        padding: 2.5rem; border-radius: 20px; margin-bottom: 2rem;
        border: 1px solid rgba(255, 255, 255, 0.05);
        text-align: center; z-index: 1;
    }
    .premium-title {
        color: #fff; font-size: 2.8rem; font-weight: 900; margin: 0;
        background: linear-gradient(135deg, #60a5fa, #a78bfa);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    .premium-lead-card {
        background: linear-gradient(135deg, #1e293b, #0f172a);
        border: 1px solid #334155; padding: 1.5rem; border-radius: 12px;
        margin: 0.5rem 0; transition: all 0.3s ease;
    }
    .premium-lead-card:hover {
        border-color: #6366f1;
        box-shadow: 0 0 28px rgba(99, 102, 241, 0.25);
        transform: translateY(-2px);
    }
    .metric-card {
        background: #1e293b; padding: 1.25rem; border-radius: 0.75rem;
        border: 1px solid #334155; text-align: center;
    }
    .glow-badge { padding: 0.35rem 0.8rem; border-radius: 30px; font-size: 0.8rem; font-weight: 700; }
    .badge-qualified-glow {
        background: rgba(16, 185, 129, 0.1); color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.4);
    }
    .badge-disqualified-glow {
        background: rgba(239, 68, 68, 0.1); color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.4);
    }
    .tier-badge {
        display: inline-block; padding: 0.25rem 0.7rem; border-radius: 20px;
        font-size: 0.72rem; font-weight: 800; margin-left: 0.5rem;
    }
    .tier-platinum { color: #e2e8f0; border: 1px solid rgba(226,232,240,0.4); }
    .tier-gold { color: #fbbf24; border: 1px solid rgba(251,191,36,0.4); }
    .tier-silver { color: #cbd5e1; border: 1px solid rgba(203,213,225,0.3); }
    .tier-bronze { color: #d97757; border: 1px solid rgba(217,119,87,0.3); }
    .reasoning-box {
        background: rgba(15, 23, 42, 0.5); padding: 1rem; border-radius: 8px;
        border-left: 4px solid #6366f1; margin-top: 1rem;
    }
    .signal-chip {
        display: inline-block; padding: 0.2rem 0.55rem; margin: 0.15rem;
        border-radius: 16px; font-size: 0.72rem; font-weight: 600;
        background: rgba(99, 102, 241, 0.15); color: #a5b4fc;
        border: 1px solid rgba(99, 102, 241, 0.3);
    }
    .pain-chip {
        background: rgba(248, 113, 113, 0.12); color: #fca5a5;
        border: 1px solid rgba(248, 113, 113, 0.3);
    }
    .activity-feed {
        background: rgba(15, 23, 42, 0.6); border: 1px solid #334155;
        border-radius: 12px; padding: 1rem; font-family: monospace; font-size: 0.82rem;
        max-height: 220px; overflow-y: auto;
    }
    .activity-line.active { color: #a78bfa; border-left: 2px solid #6366f1; padding-left: 0.6rem; }
    .skeleton-card {
        background: #1e293b; border: 1px solid #334155; border-radius: 12px;
        padding: 1.5rem; margin-bottom: 0.75rem;
    }
    .skeleton-line {
        height: 14px; border-radius: 6px; margin-bottom: 0.6rem;
        background: linear-gradient(90deg, #1e293b, #334155, #1e293b);
        background-size: 200% 100%; animation: shimmer 1.4s infinite;
    }
    .skeleton-line.short { width: 40%; }
    .skeleton-line.medium { width: 65%; }
    .skeleton-line.long { width: 90%; }
    @keyframes shimmer {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
    }
    .empty-state {
        text-align: center; padding: 4rem 2rem;
        border: 1px dashed #334155; border-radius: 16px; margin-top: 2rem;
    }
    .plan-card {
        background: rgba(30, 41, 59, 0.6); border: 1px solid #334155;
        border-radius: 16px; padding: 1.5rem; text-align: center;
        transition: transform 0.2s, border-color 0.2s;
    }
    .plan-card.featured {
        border-color: #6366f1;
        box-shadow: 0 0 30px rgba(99, 102, 241, 0.2);
    }
    .plan-card:hover { transform: translateY(-4px); }
    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
        border: none !important; font-weight: 700 !important;
    }
    .upgrade-banner {
        background: linear-gradient(135deg, rgba(99,102,241,0.15), rgba(167,139,250,0.1));
        border: 1px solid rgba(99,102,241,0.3); border-radius: 12px;
        padding: 1rem 1.25rem; margin-bottom: 1rem;
    }
    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after {
            animation-duration: 0.001ms !important;
            transition-duration: 0.001ms !important;
        }
    }
</style>
<div class="starfield"></div>
"""


def get_tier(score: int):
    if score >= 90:
        return "Platinum Lead", "tier-platinum"
    if score >= 75:
        return "Gold Lead", "tier-gold"
    if score >= 55:
        return "Silver Lead", "tier-silver"
    return "Bronze Lead", "tier-bronze"


def score_ring_html(score: int) -> str:
    _, tier_class = get_tier(score)
    colors = {"tier-platinum": "#e2e8f0", "tier-gold": "#fbbf24", "tier-silver": "#94a3b8", "tier-bronze": "#d97757"}
    color = colors.get(tier_class, "#6366f1")
    deg = round((max(0, min(score, 100)) / 100) * 360, 1)
    return (
        f'<div style="width:56px;height:56px;border-radius:50%;display:flex;align-items:center;'
        f'justify-content:center;background:conic-gradient({color} {deg}deg,#334155 0);">'
        f'<span style="font-size:0.78rem;font-weight:800;background:#0f172a;width:46px;height:46px;'
        f'border-radius:50%;display:flex;align-items:center;justify-content:center;">{score}</span></div>'
    )
