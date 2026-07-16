import streamlit as st

# Set page layout to wide and hide default headers for a native landing page feel
st.set_page_config(page_title="LeadAgent AI - Login", layout="wide", initial_sidebar_state="collapsed")

# 🎭 1. THE MOTION GRAPHICS BACKGROUND (HTML/CSS + JavaScript Canvas)
# This creates an interactive, moving fluid gradient mesh under your login box.
moving_background_html = """
<style>
    body {
        margin: 0;
        padding: 0;
        overflow: hidden;
        background: #0d0e15;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    #bg-canvas {
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        z-index: -1;
    }
</style>
<canvas id="bg-canvas"></canvas>
<script>
    const canvas = document.getElementById('bg-canvas');
    const ctx = canvas.getContext('2d');

    let width = canvas.width = window.innerWidth;
    let height = canvas.height = window.innerHeight;

    window.addEventListener('resize', () => {
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
    });

    // Configuration for the color waves
    class FluidWave {
        constructor(color, speed, amplitude, frequency) {
            this.color = color;
            this.speed = speed;
            this.amplitude = amplitude;
            this.frequency = frequency;
            this.phase = Math.random() * 100;
        }
        draw(time) {
            ctx.fillStyle = this.color;
            ctx.beginPath();
            ctx.moveTo(0, height);
            
            this.phase += this.speed;
            
            for (let x = 0; x <= width; x += 10) {
                // Generate deep moving fluid curves
                const y = height * 0.5 + 
                          Math.sin(x * this.frequency + this.phase) * this.amplitude +
                          Math.cos(x * 0.002 + this.phase * 0.5) * (this.amplitude * 0.5);
                ctx.lineTo(x, y);
            }
            
            ctx.lineTo(width, height);
            ctx.closePath();
            ctx.fill();
        }
    }

    // High-end premium palette: Deep violet, electric cyan, and soft indigo
    const waves = [
        new FluidWave('rgba(31, 18, 64, 0.8)', 0.002, 140, 0.0015),
        new FluidWave('rgba(15, 52, 89, 0.6)', 0.004, 110, 0.002),
        new FluidWave('rgba(61, 26, 91, 0.5)', 0.003, 90, 0.001),
        new FluidWave('rgba(0, 229, 255, 0.15)', 0.005, 70, 0.003) // Electric glow pop
    ];

    function animate(time) {
        // Clear canvas with a slight trail for smooth fluid rendering
        ctx.fillStyle = '#0a0b10';
        ctx.fillRect(0, 0, width, height);
        
        // Render waves stacking on top of each other
        waves.forEach(wave => wave.draw(time));
        
        requestAnimationFrame(animate);
    }
    animate(0);
</script>
"""

# Render the motion graphic canvas background behind everything
st.components.v1.html(moving_background_html, height=0, scrolling=False)

# 🎨 2. GLASSMORPHISM STYLING FOR THE INTERFACE
# Gives the login interface that premium frosted-glass blur look.
st.markdown("""
<style>
    /* target Streamlit main container */
    .stApp {
        background: transparent;
    }
    
    /* Center the login console block nicely */
    .login-container {
        background: rgba(255, 255, 255, 0.04);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 24px;
        padding: 40px;
        max-width: 480px;
        margin: 80px auto 0 auto;
        text-align: center;
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
    }
    
    h1 {
        color: #ffffff !important;
        font-weight: 800 !important;
        letter-spacing: -1px;
    }
    
    p {
        color: #a0a5c1 !important;
    }
</style>
""", unsafe_allow_html=True)

# 🏢 3. THE UI OVERLAY LAYOUT
# Empty columns to keep everything perfectly centered on desktop screens
_, center_col, _ = st.columns([1, 1.8, 1])

with center_col:
    # Wrap elements inside our glass container
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    
    st.markdown("⚡ **LEADAGENT AI**")
    st.markdown("<h1>Your next 10 enterprise clients are ready.</h1>", unsafe_allow_html=True)
    st.markdown("<p>Analyze domains, verify contact vectors, and schedule high-intent live sequences instantly.</p>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Input field
    user_email = st.text_input("Enter your work email address", placeholder="you@company.com")
    
    # Buttons row
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        if st.button("🚀 Get Started", use_container_width=True):
            if user_email:
                st.success("Authorized! Loading lead workspace...")
                st.session_state["authenticated"] = True
            else:
                st.error("Please enter a valid email address.")
                
    with btn_col2:
        st.button("🔑 Corporate SSO", use_container_width=True)
        
    st.markdown('<small style="color:#505570; display:block; margin-top:20px;">✓ Free Forever &nbsp; • &nbsp; ✓ No Credit Card &nbsp; • &nbsp; ✓ 60s Setup</small>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)