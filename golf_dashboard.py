# golf_dashboard.py — JOLF 5.0 FINAL + STROKES GAINED + ORIGINAL PANEL 4 (December 2025)
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Jolf 5.0", layout="wide")
st.title("Jolf 5.0 — Tournament SGT Dashboard")
st.caption("Private • Free • Instant")

st.info("""
**Quick note:** SGT no longer allows public data access.  
**How to get your CSV (10 seconds):**
1. Log in → Click your username → Profile
2. Click **"Download Shot Data"**
3. Drag the file below → get stats
""")

uploaded_file = st.file_uploader("Drop your SGT shot-data.csv here", type="csv")

if uploaded_file:
    with st.spinner("Loading your shots and calculating Strokes Gained..."):
        df = pd.read_csv(uploaded_file, encoding='utf-8-sig', on_bad_lines='skip')
        if df.empty:
            st.error("CSV is empty — try downloading again.")
            st.stop()
        st.session_state.df = df
        st.balloons()
        st.success(f"Loaded {len(df):,} shots • Latest: {df['Timestamp'].max()[:10]}")

if "df" not in st.session_state:
    st.stop()

df = st.session_state.df
df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
df['Date'] = df['Timestamp'].dt.date

# ===========================================================================
# STROKES GAINED SUMMARY
# ===========================================================================
st.markdown("---")
st.markdown("<h2 style='text-align: center;'>Strokes Gained Summary</h2>", unsafe_allow_html=True)

def sg_category(row):
    lie = row['Starting Lie']
    carry = row['Carry (yd)']
    if lie == 'tee':
        return 'Driving'
    elif lie in ['fairway','rough','deeprough','sand'] and carry > 50:
        return 'Approach'
    elif carry <= 50 and lie not in ['tee','green']:
        return 'Short Game'
    elif lie == 'green' and row['Gimme'] == 0:
        return 'Putting'
    else:
        return 'Other'

df['SG_Category'] = df.apply(sg_category, axis=1)

baseline = {'Driving': 3.0, 'Approach': 3.0, 'Short Game': 2.6, 'Putting': 1.5}

def strokes_taken(row):
    if row['Finish Distance To Pin'] == 0:
        return 1
    else:
        extra = row['Finish Distance To Pin'] * 3.28084 / 8 * 0.1
        return 1 + extra

df['Strokes_Taken'] = df.apply(strokes_taken, axis=1)

sg_summary = df.groupby('SG_Category').agg(
    Shots=('SG_Category', 'count'),
    Strokes_Taken=('Strokes_Taken', 'sum')
).reindex(['Driving','Approach','Short Game','Putting','Other']).fillna(0)

sg_summary['Baseline'] = sg_summary['Shots'] * sg_summary.index.map(baseline).fillna(3.0)
sg_summary['Strokes Gained'] = sg_summary['Baseline'] - sg_summary['Strokes_Taken']
sg_summary['SG/Shot'] = sg_summary['Strokes Gained'] / sg_summary['Shots'].replace(0, 1)

total_sg = sg_summary['Strokes Gained'].sum()

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("Driving", f"{sg_summary.loc['Driving','Strokes Gained']:+.2f}", f"{sg_summary.loc['Driving','SG/Shot']:+.3f}/shot")
with col2:
    st.metric("Approach", f"{sg_summary.loc['Approach','Strokes Gained']:+.2f}", f"{sg_summary.loc['Approach','SG/Shot']:+.3f}/shot")
with col3:
    st.metric("Short Game", f"{sg_summary.loc['Short Game','Strokes Gained']:+.2f}", f"{sg_summary.loc['Short Game','SG/Shot']:+.3f}/shot")
with col4:
    st.metric("Putting", f"{sg_summary.loc['Putting','Strokes Gained']:+.2f}", f"{sg_summary.loc['Putting','SG/Shot']:+.3f}/shot")
with col5:
    st.markdown(f"<h3 style='text-align:center;'>Total SG<br><span style='color:#00FF88;font-size:1.5em;'>{total_sg:+.2f}</span></h3>", unsafe_allow_html=True)

st.markdown("---")

# ===========================================================================
# 1. Approach Proximity + PGA overlay
# ===========================================================================
st.subheader("1. Approach Proximity by Distance (ft) — PGA Tour Overlay")
approaches = df[
    df['Starting Lie'].isin(['fairway', 'rough', 'deeprough', 'sand']) &
    (df['Carry (yd)'] > 50)
].copy()

if not approaches.empty:
    approaches['Band'] = pd.cut(approaches['Carry (yd)'],
                                bins=[50,75,100,125,150,175,200,225,250,1000],
                                labels=['50-75','75-100','100-125','125-150','150-175','175-200','200-225','225-250','250+'])
    prox = approaches.groupby('Band', observed=True)['Finish Distance To Pin'].agg(['mean','count']).reset_index()
    prox['mean_ft'] = prox['mean'] * 3.28084
    prox['Label'] = prox['mean_ft'].round(1).astype(str) + "ft (" + prox['count'].astype(str) + ")"

    pga_ft = [15, 22, 30, 39, 50, 62, 75, 90, 110]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=prox['Band'], y=prox['mean_ft'], name="You", text=prox['Label'], marker_color="#00ff88"))
    fig.add_trace(go.Scatter(x=prox['Band'], y=pga_ft, mode="lines+markers", name="PGA Tour Avg", line=dict(color="red", dash="dash", width=3)))
    fig.update_layout(title="Your Proximity vs PGA Tour", yaxis_title="Feet to Pin", template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)

# ===========================================================================
# Two-column layout
# ===========================================================================
col1, col2 = st.columns(2)

with col1:
    # 2. Heatmap
    if not approaches.empty:
        pivot = approaches.pivot_table(values='Finish Distance To Pin', index='Band', columns='Starting Lie', aggfunc='mean', observed=True) * 3.28084
        fig = go.Figure(data=go.Heatmap(z=pivot.values, x=pivot.columns, y=pivot.index,
                                        colorscale='Portland', text=pivot.values.round(1), texttemplate="%{text}ft"))
        fig.update_layout(title="2. Proximity Heatmap (ft)", template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

    # 3. 100–150 yd dispersion
    mid = approaches[approaches['Carry (yd)'].between(100, 150)]
    if not mid.empty:
        fig = px.scatter(mid, x='HLA (deg)', y='Finish Distance To Pin', color='Spin Axis (deg)', size='Ballspeed (mph)',
                         title="3. 100–150 yd Shot Pattern", template="plotly_dark")
        fig.add_vline(x=0, line_dash="dash")
        st.plotly_chart(fig, use_container_width=True)

with col2:
    # 4. ORIGINAL PANEL 4 — DRIVE DISTANCE BY HOLE (PER ROUND, ONLY DRIVER HOLES)
    st.subheader("4. Drive Distance by Hole — Per Round View")
    drives = df[df['Starting Lie'] == 'tee'].copy()

    if not drives.empty:
        # Only show holes where driver was actually used
        holes_with_driver = drives['Hole'].value_counts()
        holes_with_driver = holes_with_driver[holes_with_driver > 0].index.tolist()
        drives = drives[drives['Hole'].isin(holes_with_driver)]

        # Create nice round label
        drives['Round'] = drives['Timestamp'].dt.strftime('%Y-%m-%d') + " — " + drives['Course'].fillna('Unknown Course')

        fig = px.box(
            drives,
            x='Hole',
            y='Total Distance (yd)',
            color='Round',
            title="Drive Distance by Hole — Only Holes Where Driver Was Used",
            labels={'Total Distance (yd)': 'Total Distance (yards)'},
            template="plotly_dark",
            hover_data=['Course', 'Timestamp']
        )
        fig.update_xaxes(type='category', title="Hole Number")
        fig.update_layout(showlegend=True, legend_title="Round", height=600)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No driver shots found in this data")

    # 5. Launch efficiency
    if not drives.empty:
        fig = px.scatter(drives, x='VLA (deg)', y='Ballspeed (mph)', color='Total Distance (yd)', size='Carry (yd)',
                         title="5. Driver Efficiency Zone", template="plotly_dark")
        fig.add_vrect(x0=11, x1=14, fillcolor="green", opacity=0.2)
        fig.add_hrect(y0=160, y1=175, fillcolor="green", opacity=0.2)
        st.plotly_chart(fig, use_container_width=True)

# ===========================================================================
# 6. Putt Make % — FIXED & BEAUTIFUL
# ===========================================================================
st.subheader("6. Putt Make % — With Sample Size & PGA Comparison")
putts = df[(df['Starting Lie'] == 'green') & (df['Gimme'] == 0)]
if not putts.empty:
    putts['Band'] = pd.cut(putts['Total Distance (yd)'],
                           bins=[0,3,6,10,15,20,30,50],
                           labels=['0-3','3-6','6-10','10-15','15-20','20-30','30-50'])
    stats = putts.groupby('Band', observed=True).agg(
        made=('Finish Distance To Pin', lambda x: (x == 0).sum()),
        total=('Finish Distance To Pin', 'count')
    ).reset_index()
    stats['% Made'] = (stats['made'] / stats['total']) * 100
    stats['Label'] = stats['% Made'].round(1).astype(str) + "% (" + stats['made'].astype(str) + "/" + stats['total'].astype(str) + ")"

    pga = [98, 85, 60, 36, 22, 12, 5]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=stats['Band'], y=stats['% Made'], name="You", text=stats['Label'], marker_color="#00FF88"))
    fig.add_trace(go.Scatter(x=stats['Band'], y=pga, mode="lines+markers", name="PGA Tour Avg", line=dict(color="gold", dash="dash", width=3)))
    fig.update_layout(title="Putt Make % by Distance", yaxis_title="% Made", template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No putts recorded (or all were gimmes)")

# ===========================================================================
# Remaining panels
# ===========================================================================
st.subheader("7. Drive Dispersion – Last 50")
if 'drives' in locals() and not drives.empty:
    recent = drives.tail(50)
    fig = px.scatter_polar(recent, r='Carry (yd)', theta='HLA (deg)', color='Spin Axis (deg)', size='Ballspeed (mph)',
                           title="Drive Dispersion Pattern", template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)

st.subheader("8. Where Shots End Up")
ct = pd.crosstab(df['Starting Lie'], df['Finishing Lie'], normalize='index') * 100
fig = px.bar(ct.reset_index().melt(id_vars='Starting Lie'), x='Starting Lie', y='value', color='Finishing Lie',
             title="Finishing Lie % by Starting Lie", template="plotly_dark")
st.plotly_chart(fig, use_container_width=True)

st.subheader("9. Career Shot Volume - Placeholder for long trend")
cumulative = df.groupby('Date').size().cumsum().reset_index(name='Total Shots')
fig = px.area(cumulative, x='Date', y='Total Shots', title="Total Shots Logged Over Time", template="plotly_dark")
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.caption("Jolf 5.0 • Built with love by rossbrandenburg • December 2025")