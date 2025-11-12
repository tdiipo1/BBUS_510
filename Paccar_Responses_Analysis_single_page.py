# PACCAR Survey Hypothesis Tester — v8
# Enhancements: dark chart background polish, multi-select filters, per-chart data tables + CSV download
# Run: streamlit run paccar_survey_app_v8.py

import re, numpy as np, pandas as pd, matplotlib.pyplot as plt, streamlit as st
from scipy import stats
import statsmodels.api as sm
from io import BytesIO

# Optional deps for open text
WORDCLOUD_AVAILABLE = False
SENTIMENT_VADER_AVAILABLE = False
try:
    from wordcloud import WordCloud, STOPWORDS as WC_STOPWORDS
    WORDCLOUD_AVAILABLE = True
except Exception:
    pass
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    SENTIMENT_VADER_AVAILABLE = True
except Exception:
    pass

# ---------------- UI / Theme ----------------
st.set_page_config(page_title="UW Bothell B BUS 510 — PACCAR Survey Hypothesis Tester (v8)", layout="wide")

def is_dark_mode():
    try:
        return str(st.get_option("theme.base")).lower() == "dark"
    except Exception:
        return False

DARK = is_dark_mode()

def apply_mpl_theme():
    bg = "#0E1117" if DARK else "#FFFFFF"
    fg = "#FAFAFA" if DARK else "#0E1117"
    grid = "#2A2F3B" if DARK else "#E6E6E6"
    plt.rcParams.update({
        "figure.facecolor": bg, "axes.facecolor": bg, "savefig.facecolor": bg,
        "axes.edgecolor": grid, "axes.labelcolor": fg, "text.color": fg,
        "xtick.color": fg, "ytick.color": fg, "grid.color": grid,
        "axes.grid": True, "grid.alpha": 0.25 if DARK else 0.35, "font.size": 12
    })
apply_mpl_theme()

# ---------------- Header ----------------
st.markdown("""
### University of Washington Bothell — **B BUS 510 (Managing Organizational Effectiveness)**
**Group B4 Team Project Paper** — *PACCAR Purchasing Systems Survey*
""")
st.title("Survey Hypothesis Tester (v8)")
st.caption("Dark-mode polished charts, multi-select filters, and per-chart data tables with CSV downloads.")

# ---------------- Likert helpers ----------------
LIKERT = {
    "strongly disagree": 1, "disagree": 2, "neither agree nor disagree": 3,
    "neutral": 3, "agree": 4, "strongly agree": 5,
    "very cumbersome": 1, "somewhat cumbersome": 2, "somewhat cumebersome": 2,
    "neither cumbersome nor easy": 3, "somewhat easy": 4, "very easy": 5,
}
def to_15(x):
    if pd.isna(x): return np.nan
    x = str(x).strip()
    v = pd.to_numeric(x, errors="coerce")
    if not pd.isna(v): return float(v)
    return float(LIKERT.get(x.lower(), np.nan))

def inv_15(series):
    return series.apply(lambda v: np.nan if pd.isna(v) else 6 - v)

def status_from_score(x):
    if pd.isna(x): return "–"
    if x >= 3.5: return "✅ Good"
    if x >= 2.5: return "⚠️ Watch"
    return "❌ Risk"

# ---------------- Expected headers ----------------
COL_ROLE      = "Your role: "
COL_DIV       = "Division / scope:"
COL_SYSTEMS   = "Primary systems you touch weekly (check all): "

Q4_IC         = "I (or my group) were involved early enough (requirements, testing) in the last rollout of ICERTIS/SPM ARIBA affecting me - ICERTIS"
Q4_AR         = "I (or my group) were involved early enough (requirements, testing) in the last rollout of ICERTIS/SPM ARIBA affecting me - SPM ARIBA"
Q5_IC         = "I understood the “why” (benefits, pain points solved) before go-live - ICERTIS"
Q5_AR         = "I understood the “why” (benefits, pain points solved) before go-live - SPM ARIBA"
Q6_MANDATE    = "My manager/leadership set clear expectations to use the new system(s) as the single source of record"
Q6_BLOCKERS   = 'If you choose "strongly disagree/disagree" What blocked that?'
Q7_IC         = "The training I received on ICERTIS/ARIBA/ MADR was sufficient and timely - Icertis"
Q7_AR         = "The training I received on ICERTIS/ARIBA/ MADR was sufficient and timely - SAP ARIBA"
Q7_MF         = "The training I received on ICERTIS/ARIBA/ MADR was sufficient and timely - Mainframe/MADR"
Q8_IC         = "For my common tasks, the system feels… - ICETIS"
Q8_AR         = "For my common tasks, the system feels… - SPM ARIBA"
Q8_MF         = "For my common tasks, the system feels… - Mainframe/MADR"
Q9_PRESSURE   = "When I’m under time pressure, I can still complete tasks in the system without reverting to old methods."
Q10_INFO      = "The information I need (prices, terms, agreements) is accurate and complete where I expect to find it. "
Q14_HELP      = '\"Which would help you most in staying on the “happy path”? (Pick two) \\n \\n \\n \"'
Q15_CHANGE    = 'If you could change one thing in the workflow tomorrow, what would it be and why?'

# ---------------- Template (download) ----------------
st.sidebar.header("Template")
template_cols = [
    "ID","Start time","Completion time","Email","Name","Last modified time",
    COL_ROLE, COL_DIV, COL_SYSTEMS,
    Q4_IC, Q4_AR, Q5_IC, Q5_AR, Q6_MANDATE, Q6_BLOCKERS,
    Q7_IC, Q7_AR, Q7_MF, Q8_IC, Q8_AR, Q8_MF, Q9_PRESSURE, Q10_INFO, Q14_HELP, Q15_CHANGE
]
template_df = pd.DataFrame(columns=template_cols)
buf = BytesIO()
with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
    template_df.to_excel(writer, index=False, sheet_name="SurveyTemplate")
    writer.sheets["SurveyTemplate"].set_column(0, len(template_cols)-1, 28)
st.sidebar.download_button("Download XLSX Template", buf.getvalue(), file_name="PACCAR_Survey_Template.xlsx")

# ---------------- Upload ----------------
file = st.file_uploader("Drop your survey export (.xlsx)", type=["xlsx"])
if not file:
    st.info("Upload the Excel export to begin.")
    st.stop()
df_raw = pd.read_excel(file)
df = df_raw.copy()

# ---------------- Coerce to numeric ----------------
for col in [Q4_IC,Q4_AR,Q5_IC,Q5_AR,Q6_MANDATE,Q7_IC,Q7_AR,Q7_MF,Q9_PRESSURE,Q10_INFO]:
    if col in df.columns: df[col+"_n"] = df[col].map(to_15)
for col in [Q8_IC,Q8_AR,Q8_MF]:
    if col in df.columns: df[col+"_n"] = inv_15(df[col].map(to_15))

# ---------------- Indices ----------------
def mean_cols(cols):
    cols = [c for c in cols if c in df.columns]
    return df[cols].mean(axis=1) if cols else np.nan

df["H1_involvement"] = mean_cols([Q4_IC+"_n",Q4_AR+"_n",Q5_IC+"_n",Q5_AR+"_n",Q6_MANDATE+"_n"])
df["H2_friction"]    = mean_cols([Q7_IC+"_n",Q7_AR+"_n",Q7_MF+"_n",Q8_IC+"_n",Q8_AR+"_n",Q8_MF+"_n",Q9_PRESSURE+"_n"])
df["H3_integrity"]   = mean_cols([Q10_INFO+"_n"])
df["H4_governance"]  = df.get(Q6_MANDATE+"_n", np.nan)

# Derived flags
df["Workaround"] = df.get(Q9_PRESSURE+"_n", pd.Series(np.nan, index=df.index)) <= 3
df["AnyIssue"]   = False  # Q12 not in this batch

# ---------------- Filters (multi-select) ----------------
st.sidebar.header("Filters")
def multiselect_all(label, options):
    if not options: return []
    return st.sidebar.multiselect(label, options=options, default=options)

roles_avail = sorted(df.get(COL_ROLE, pd.Series([], dtype=object)).dropna().unique().tolist())
divs_avail  = sorted(df.get(COL_DIV, pd.Series([], dtype=object)).dropna().unique().tolist())
systems_av  = sorted(set(sum([str(x).split(";") for x in df.get(COL_SYSTEMS, pd.Series([], dtype=object)).dropna().tolist()], [])))
systems_av  = [s for s in systems_av if s and s != "nan"]

sel_roles   = multiselect_all("Roles", roles_avail)
sel_divs    = multiselect_all("Divisions", divs_avail)
sel_systems = multiselect_all("Systems", systems_av)

df_f = df.copy()
if sel_roles:   df_f = df_f[df_f[COL_ROLE].isin(sel_roles)]
if sel_divs:    df_f = df_f[df_f[COL_DIV].isin(sel_divs)]
if sel_systems and COL_SYSTEMS in df_f.columns:
    df_f = df_f[df_f[COL_SYSTEMS].fillna("").apply(lambda s: any(sys in s for sys in sel_systems))]

# ---------------- Executive Summary ----------------
avg_H1 = float(np.nanmean(df_f["H1_involvement"])) if len(df_f) else np.nan
avg_H2 = float(np.nanmean(df_f["H2_friction"])) if len(df_f) else np.nan
avg_H3 = float(np.nanmean(df_f["H3_integrity"])) if len(df_f) else np.nan
avg_H4 = float(np.nanmean(df_f["H4_governance"])) if len(df_f) else np.nan
rate_issue = float(df_f["AnyIssue"].mean()) if len(df_f) else 0.0

st.markdown("### Executive Summary")
c1,c2,c3 = st.columns([1,2,2])
with c1:
    st.metric("Responses", len(df_f))
with c2:
    st.markdown(f"**Early Involvement & Understanding (H1):** {avg_H1:.2f} / 5 — {status_from_score(avg_H1)}  \n"
                f"**Training & Usability (H2):** {avg_H2:.2f} / 5 — {status_from_score(avg_H2)}  \n"
                f"**Data Confidence (H3):** {avg_H3:.2f} / 5 — {status_from_score(avg_H3)}")
with c3:
    st.markdown(f"**Leadership Mandate Clarity (H4):** {avg_H4:.2f} / 5 — {status_from_score(avg_H4)}  \n"
                f"**Any Issue Rate (Q12):** {rate_issue:.0%}  _(not collected in this batch)_")

# ---------------- Distributions (1=worst → 5=best) ----------------
st.markdown("### Distributions (1=worst → 5=best)")
PALETTE = [(1.0, 0.2, 0.2), (1.0, 0.5, 0.3), (0.9, 0.8, 0.4), (0.4, 0.7, 0.9), (0.2, 0.4, 1.0)]

def plot_likert_counts(series, title):
    s = pd.to_numeric(series, errors="coerce").dropna().astype(float)
    if s.empty:
        st.info(f"No data for {title}."); return None
    counts = pd.Series({k: (s==k).sum() for k in [1,2,3,4,5]})
    fig, ax = plt.subplots()
    fig.patch.set_facecolor("#0E1117" if DARK else "#FFFFFF")
    ax.set_facecolor("#0E1117" if DARK else "#FFFFFF")
    ax.bar(counts.index.astype(int), counts.values, color=PALETTE, edgecolor="none")
    ax.set_xticks([1,2,3,4,5]); ax.set_xlabel("Score"); ax.set_ylabel("Responses")
    ax.set_title(title, pad=10); ax.grid(axis="y", alpha=0.25 if DARK else 0.35)
    st.pyplot(fig)
    return counts

def chart_block(series, title, caption_tag):
    counts = plot_likert_counts(series, title)
    if counts is None: return
    with st.expander("Show data"):
        st.dataframe(counts.rename("Count").to_frame().rename_axis("Score").reset_index())
        csv = counts.rename("Count").to_csv(index=False).encode("utf-8")
        st.download_button("Download this chart data (CSV)", csv, file_name=f"{caption_tag}_counts.csv")
    st.caption(caption_tag)

chart_block(df_f["H1_involvement"], "Early Involvement & Understanding (H1)", "Lower H1 often correlates with higher workaround behavior.")
chart_block(df_f["H2_friction"],    "Training & Usability (H2)",             "Lower H2 indicates friction (training or UX) that pushes users off the happy path.")
chart_block(df_f["H3_integrity"],   "Data Confidence (H3)",                  "If this is low, integration/data quality needs attention.")
chart_block(df_f["H4_governance"],  "Mandate Clarity (H4)",                  "Lower H4 suggests inconsistent leadership messaging on 'single source of record'.")

# ---------------- Segment summary ----------------
st.markdown("### Segment summary (Role × Division)")
if len(df_f):
    seg = (df_f
           .groupby([COL_ROLE, COL_DIV], dropna=False)
           .agg(n=("H1_involvement","count"),
                H1=("H1_involvement","mean"),
                H2=("H2_friction","mean"),
                H3=("H3_integrity","mean"),
                H4=("H4_governance","mean"),
                AnyIssue=("AnyIssue","mean"),
                Workaround=("Workaround","mean"))
           .reset_index())
    st.dataframe(seg)
else:
    st.info("No rows after filters.")

# ---------------- Hypothesis tests ----------------
st.markdown("### Hypothesis tests")
df_f["LowH1"] = df_f["H1_involvement"] < 3
h1_ct = pd.crosstab(df_f["LowH1"].fillna(False), df_f["Workaround"].fillna(False))
st.markdown("**H1 — Involvement → Workarounds (chi-square)**")
st.dataframe(h1_ct)
if h1_ct.shape == (2,2) and h1_ct.values.sum() > 0:
    chi2, p, dof, _ = stats.chi2_contingency(h1_ct)
    st.write(f"chi2={chi2:.3f}, p={p:.4f}, dof={dof}")
    st.caption("Interpretation: p<0.05 suggests lower involvement is associated with higher workaround behavior.")

df_f["LowH2"] = df_f["H2_friction"] < 3
st.markdown("**H2 — Friction → Under-pressure behavior (t-test on Q9)**")
q9 = df_f.get(Q9_PRESSURE+"_n", pd.Series(np.nan, index=df_f.index))
g1 = q9[df_f["LowH2"]==True].dropna()
g2 = q9[df_f["LowH2"]==False].dropna()
if len(g1) > 1 and len(g2) > 1:
    t = stats.ttest_ind(g1, g2, equal_var=False)
    st.write({"mean_Q9_lowH2": float(g1.mean()), "mean_Q9_highH2": float(g2.mean()),
              "t": float(t.statistic), "p": float(t.pvalue)})
    st.caption("Interpretation: If mean_Q9_lowH2 < mean_Q9_highH2 and p<0.05, friction likely increases reversion under pressure.")
else:
    st.info("Not enough responses to run H2 t-test in current filters.")

st.markdown("**H3 — Data confidence → Issues (logit)**")
if df_f["AnyIssue"].any():
    try:
        y = df_f["AnyIssue"].astype(int)
        X = pd.DataFrame({"const":1.0, "H3": df_f["H3_integrity"].astype(float).fillna(df_f["H3_integrity"].mean())})
        model = sm.Logit(y, X).fit(disp=False)
        st.text(model.summary().as_text())
        st.caption("Interpretation: Significant negative coefficient on H3 means better data confidence lowers issue probability.")
    except Exception as e:
        st.info(f"Could not fit model: {e}")
else:
    st.info("Skipped: Q12 issue flags not present in this export.")

st.markdown("**H4 — Mandate clarity → Issues (chi-square)**")
df_f["LowH4"] = df_f["H4_governance"] < 3
h4_ct = pd.crosstab(df_f["LowH4"].fillna(False), df_f["AnyIssue"].fillna(False))
st.dataframe(h4_ct)
st.caption("Interpretation: Will be meaningful when Q12 is added; currently, AnyIssue is not collected in this batch.")

# ---------------- Open Text Analysis (Q15) ----------------
st.markdown("---")
st.markdown("## Open Text Feedback Analysis (Q15)")
text_col = Q15_CHANGE if Q15_CHANGE in df_f.columns else None
if text_col is None:
    st.info("No open-text column found in this export.")
else:
    texts = df_f[text_col].dropna().astype(str)
    st.write(f"Responses with text: **{len(texts)}**")

    base_stop = {"the","and","a","to","of","in","for","on","at","it","is","be","that","this","with","as",
                 "by","or","an","are","from","we","our","your","you","i","me","my","their","they","he","she",
                 "will","would","should","could","can","if","than","then","there","here","so","not","no","yes",
                 "one","thing","things","time","day","work","workflow","tomorrow","why"}
    domain_stop = {"icertis","spm","ariba","gpps","sap","madr","system","systems","document","documents","process","processes"}
    stopwords = base_stop.union(domain_stop)

    def tokenize(s):
        tokens = re.findall(r"[A-Za-z][A-Za-z\-']+", s.lower())
        return [t for t in tokens if t not in stopwords and len(t) > 2]

    tokens = [t for text in texts for t in tokenize(text)]
    unigrams = pd.Series(tokens).value_counts().head(20) if len(tokens) else pd.Series(dtype=int)
    bigrams = []
    for s in texts:
        toks = tokenize(s)
        bigrams += [" ".join(pair) for pair in zip(toks, toks[1:])]
    bigrams = pd.Series(bigrams).value_counts().head(15) if bigrams else pd.Series(dtype=int)

    st.markdown("### Key Themes")
    if len(tokens)==0:
        st.info("No tokens to analyze.")
    else:
        if WORDCLOUD_AVAILABLE:
            try:
                wc = WordCloud(width=900, height=450, background_color=("black" if DARK else "white")).generate(" ".join(tokens))
                fig, ax = plt.subplots(figsize=(9, 4.8))
                fig.patch.set_facecolor("#0E1117" if DARK else "#FFFFFF")
                ax.set_facecolor("#0E1117" if DARK else "#FFFFFF")
                ax.imshow(wc, interpolation="bilinear"); ax.axis("off")
                st.pyplot(fig)
            except Exception:
                pass
        if not unigrams.empty:
            fig, ax = plt.subplots(figsize=(8,5))
            fig.patch.set_facecolor("#0E1117" if DARK else "#FFFFFF")
            ax.set_facecolor("#0E1117" if DARK else "#FFFFFF")
            unigrams.iloc[::-1].plot(kind="barh", ax=ax, color="#6AA6FF"); ax.set_title("Top keywords"); ax.set_xlabel("Count")
            st.pyplot(fig)
        if not bigrams.empty:
            fig, ax = plt.subplots(figsize=(8,5))
            fig.patch.set_facecolor("#0E1117" if DARK else "#FFFFFF")
            ax.set_facecolor("#0E1117" if DARK else "#FFFFFF")
            bigrams.iloc[::-1].plot(kind="barh", ax=ax, color="#6AA6FF"); ax.set_title("Top phrases"); ax.set_xlabel("Count")
            st.pyplot(fig)

    st.markdown("### Sentiment")
    sentiments = None
    if SENTIMENT_VADER_AVAILABLE:
        try:
            analyzer = SentimentIntensityAnalyzer()
            sentiments = texts.apply(lambda t: analyzer.polarity_scores(t)["compound"])
        except Exception:
            pass
    if sentiments is None:
        pos = {"fast","faster","improve","better","easy","easier","clear","helpful","streamline","reduce"}
        neg = {"slow","slower","delay","delays","difficult","hard","confusing","cumbersome","errors","overcomplicate","complicate","frustrating"}
        def simple_sent(t):
            toks = tokenize(t)
            score = sum(1 if w in pos else -1 if w in neg else 0 for w in toks)
            return score / max(1, len(toks))
        sentiments = texts.apply(simple_sent)

    fig, ax = plt.subplots(figsize=(7,4))
    fig.patch.set_facecolor("#0E1117" if DARK else "#FFFFFF")
    ax.set_facecolor("#0E1117" if DARK else "#FFFFFF")
    ax.hist(sentiments, bins=10, edgecolor="none", color="#6AA6FF")
    ax.set_title("Sentiment distribution (negative ← 0 → positive)"); ax.set_xlabel("Sentiment score"); ax.set_ylabel("Responses")
    st.pyplot(fig)
    st.write(f"**Average sentiment:** {sentiments.mean():.3f}  |  **Median:** {sentiments.median():.3f}")

    st.markdown("### Themes mapped to hypotheses (H1–H4)")
    theme_map = {
        "involve":"H1","requirements":"H1","testing":"H1","early":"H1",
        "training":"H2","learn":"H2","usability":"H2","cumbersome":"H2","clicks":"H2","speed":"H2","faster":"H2","slow":"H2","step":"H2","steps":"H2","guid":"H2",
        "data":"H3","integrat":"H3","duplicate":"H3","pricing":"H3","invoice":"H3","mismatch":"H3",
        "mandate":"H4","single":"H4","source":"H4","record":"H4","policy":"H4",
    }
    def map_themes(text):
        t = text.lower(); hits = {tag for k,tag in theme_map.items() if k in t}
        return sorted(hits) if hits else ["Uncategorized"]
    themed_rows = []
    for _, r in df_f[df_f.get(Q15_CHANGE, "").astype(str)!=""].iterrows():
        for th in map_themes(r[Q15_CHANGE]):
            themed_rows.append({"Theme": th, "Text": r[Q15_CHANGE]})
    if themed_rows:
        theme_df = pd.DataFrame(themed_rows)
        counts = theme_df["Theme"].value_counts().rename_axis("Theme").reset_index(name="Count")
        c1,c2 = st.columns([1,2])
        with c1:
            fig, ax = plt.subplots(figsize=(6,4))
            fig.patch.set_facecolor("#0E1117" if DARK else "#FFFFFF")
            ax.set_facecolor("#0E1117" if DARK else "#FFFFFF")
            counts.set_index("Theme")["Count"].iloc[::-1].plot(kind="barh", ax=ax, color="#6AA6FF")
            ax.set_title("Theme frequency"); ax.set_xlabel("Count")
            st.pyplot(fig)
        with c2:
            st.dataframe(theme_df.sample(min(len(theme_df), 10), random_state=42))
        st.download_button("Download theme mapping (CSV)", theme_df.to_csv(index=False).encode("utf-8"),
                           file_name="open_text_theme_mapping.csv")
    else:
        st.info("No mappable themes found in open-text responses.")

# ---------------- Downloads ----------------
st.markdown("### Downloads")
scored = df_f[[COL_ROLE, COL_DIV, "H1_involvement","H2_friction","H3_integrity","H4_governance","Workaround","AnyIssue"]].copy()
st.download_button("Download scored responses (CSV)", scored.to_csv(index=False).encode("utf-8"),
                   file_name="responses_scored_v8.csv")
 