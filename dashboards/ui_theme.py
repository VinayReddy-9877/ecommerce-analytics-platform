"""Shared presentation settings; no warehouse or metric logic lives here."""

import plotly.io as pio
import streamlit as st


def apply_theme():
    pio.templates["olist"] = pio.templates["plotly_white"]
    pio.templates["olist"].layout.update(
        font=dict(family="Arial, sans-serif", color="#24364B", size=13),
        colorway=["#087F8C", "#60758D", "#B77935", "#89B8B6"],
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        margin=dict(l=20, r=25, t=30, b=35),
        xaxis=dict(gridcolor="#E8EDF2", zeroline=False),
        yaxis=dict(gridcolor="#E8EDF2", zeroline=False),
        legend=dict(orientation="h", y=1.15, x=0),
    )
    pio.templates.default = "olist"
    st.markdown(
        """
    <style>
      .stApp {background:#E9EEF4;color:#172B46;}
      [data-testid="stHeader"] {background:#E9EEF4;}
      .block-container {padding-top:2rem;max-width:1530px;padding-bottom:3rem;}
      h1,h2,h3 {color:#142B46;letter-spacing:-.025em;}
      h1 {font-size:2.15rem!important;}
      h3 {font-size:1.15rem!important;}
      [data-testid="stSidebar"] {background:#14283F;}
      [data-testid="stSidebar"] p,
      [data-testid="stSidebar"] h2,
      [data-testid="stSidebar"] label,
      [data-testid="stSidebar"] span {color:#E8EFF7!important;}
      [data-testid="stMetric"] {background:white;border:1px solid #DCE4ED;
        padding:20px 22px;border-radius:10px;}
      [data-testid="stMetric"] * {color:#172B46!important;}
      [data-testid="stMetricValue"] {font-size:2rem!important;font-weight:600;}
      [data-testid="stVerticalBlockBorderWrapper"]>div {
        border-color:#DCE4ED!important;border-radius:10px;background:#FFFFFF;}
      [data-testid="stCaptionContainer"] {color:#56697D;}
      .brand {font-size:24px;font-weight:700;letter-spacing:.02em;margin:0 0 4px;}
      .brand-note {color:#ACBDD0;font-size:12px;margin-bottom:25px;}
    </style>
    """,
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        '<div class="brand">olist / analytics</div><div class="brand-note">COMMERCE • CUSTOMER • OPERATIONS</div>',
        unsafe_allow_html=True,
    )
