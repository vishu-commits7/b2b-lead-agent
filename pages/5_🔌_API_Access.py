"""REST API key management for Pro and Enterprise plans."""

import streamlit as st

from database import create_api_key, list_api_keys, revoke_api_key
from services.plans import feature_enabled
from ui.auth_guard import init_session, require_auth, sidebar_user_menu
from ui.theme import ENTERPRISE_CSS

st.set_page_config(page_title="API Access | LeadAgent.io", layout="wide")
init_session()
require_auth()

st.markdown(ENTERPRISE_CSS, unsafe_allow_html=True)
st.sidebar.title("API Access")
sidebar_user_menu()

user_id = st.session_state.user_id
plan = st.session_state.user_plan

st.markdown("# 🔌 REST API Access")

if not feature_enabled(plan, "api_access"):
    st.warning("REST API access requires a **Pro** or **Enterprise** plan.")
    st.page_link("pages/3_💳_Pricing.py", label="→ View Pricing")
    st.stop()

st.markdown("""
Programmatic access to LeadAgent.io. Use your API key in the `Authorization` header:

```
Authorization: Bearer la_your_api_key_here
```

**Endpoints** (run `uvicorn api.server:app --port 8000`):
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/runs` | Start a discovery pipeline |
| GET | `/api/v1/runs` | List your runs |
| GET | `/api/v1/runs/{id}/leads` | Get leads from a run |
| GET | `/api/v1/health` | Health check |
""")

if "new_api_key" not in st.session_state:
    st.session_state.new_api_key = None

label = st.text_input("Key label", value="Production")
if st.button("Generate New API Key", type="primary"):
    raw = create_api_key(user_id, label=label)
    st.session_state.new_api_key = raw
    st.success("Key created — copy it now. It won't be shown again.")

if st.session_state.new_api_key:
    st.code(st.session_state.new_api_key, language=None)

st.markdown("---")
st.markdown("### Active Keys")
keys = list_api_keys(user_id)
if not keys:
    st.info("No API keys yet.")
else:
    for k in keys:
        col1, col2, col3 = st.columns([3, 2, 1])
        col1.markdown(f"**{k['label']}** — `{k['key_prefix']}...`")
        last = "Never" if not k.get("last_used_at") else "Recently used"
        col2.caption(last)
        if not k.get("revoked") and col3.button("Revoke", key=f"rev_{k['id']}"):
            revoke_api_key(user_id, k["id"])
            st.rerun()
