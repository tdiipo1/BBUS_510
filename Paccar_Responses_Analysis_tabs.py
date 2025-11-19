# Save this as survey_app.py (REPLACE YOUR OLD FILE)
import streamlit as st
import pandas as pd
import altair as alt
import numpy as np
from io import BytesIO
import os

# --- NEW LIBRARIES (Install vaderSentiment) ---
from wordcloud import WordCloud, STOPWORDS
import matplotlib.pyplot as plt
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
# --- END NEW ---

# --- 1. USER CONFIGURATION ---
COLUMN_MAPPING = {
    # --- Demographics ---
    'Q1_Role': 'Your role: ',
    'Q2_Division': 'Division / scope:',
    'Q3_Systems': 'Primary systems you touch weekly (check all): ',

    # --- H1: Involvement (Q4-Q6) ---
    'Q4_Involvement_Icertis': 'I (or my group) were involved early enough (requirements, testing) in the last rollout of ICERTIS/SPM ARIBA affecting me - ICERTIS',
    'Q4_Involvement_Ariba': 'I (or my group) were involved early enough (requirements, testing) in the last rollout of ICERTIS/SPM ARIBA affecting me - SPM ARIBA',
    'Q5_Why_Icertis': 'I understood the “why” (benefits, pain points solved) before go-live - ICERTIS',
    'Q5_Why_Ariba': 'I understood the “why” (benefits, pain points solved) before go-live - SPM ARIBA',
    'Q6_Mandate': 'My manager/leadership set clear expectations to use the new system(s) as the single source of record',
    'Q6_1_Blockers': 'If you choose "strongly disagree/disagree" What blocked that?',

    # --- H2: Friction (Q7-Q9) ---
    'Q7_Training_Icertis': 'The training I received on ICERTIS/ARIBA/ MADR was sufficient and timely - Icertis',
    'Q7_Training_Ariba': 'The training I received on ICERTIS/ARIBA/ MADR was sufficient and timely - SAP ARIBA',
    'Q7_Training_Mainframe': 'The training I received on ICERTIS/ARIBA/ MADR was sufficient and timely - Mainframe/MADR',
    'Q8_Usability_Icertis': 'For my common tasks, the system feels… - ICETIS',
    'Q8_Usability_Ariba': 'For my common tasks, the system feels… - SPM ARIBA',
    'Q8_Usability_Mainframe': 'For my common tasks, the system feels… - Mainframe/MADR',
    'Q9_TimePressure': 'When I’m under time pressure, I can still complete tasks in the system without reverting to old methods.',

    # --- H3: Integrity (Q10) ---
    'Q10_Accuracy': 'The information I need (prices, terms, agreements) is accurate and complete where I expect to find it. ',

    # --- H4: Fixes (Q14-Q15) ---
    'Q14_HelpMost': 'Which would help you most in staying on the “happy path”? (Pick two) \n \n ',
    'Q15_OpenText': 'If you could change one thing in the workflow tomorrow, what would it be and why?'
}

LIKERT_ORDER = [
    "Strongly disagree", "Disagree", 
    "Neither agree nor disagree", "Neutral", 
    "Agree", "Strongly agree"
]

USABILITY_ORDER = [
    "Very Cumbersome", "Somewhat Cumebersome", # Typo matches data
    "Neither Cumbersome nor Easy", "Somewhat Easy", "Very Easy"
]

THEME_KEYWORDS = {
    'H2_Usability_Friction': ['slow', 'easy', 'easier', 'cumbersome', 'clicks', 'hoops', 'overcomplicates', 'speed', 'user friendly', 'long', 'faster', 'steps', 'administrative', 'intuitive', 'not easy to use'],
    'H2_Training_Friction': ['training', 'videos', 'instructions', 'guided', 'on-boarding', 'documentation'],
    'H1_Involvement_Value': ['old system', 'go back', 'value', 'why', 'prefer... manually', 'purpose'],
    'H3_Data_Integrity': ['find', 'search', 'accurate', 'data', 'reporting', 'information', 'linking'],
    'Collaboration_Feature': ['multiple users', 'editors', 'simultaneously', 'reviewing', 'sharing', 'approval process']
}
# --- END OF CONFIGURATION ---


@st.cache_data
def create_template_excel():
    """Creates an in-memory Excel file with the required headers and 3 sample rows."""
    columns = [
        "ID", "Start time", "Completion time", "Email", "Name", "Last modified time",
        "Your role: ", "Division / scope:", "Primary systems you touch weekly (check all): ",
        "I (or my group) were involved early enough (requirements, testing) in the last rollout of ICERTIS/SPM ARIBA affecting me - ICERTIS",
        "I (or my group) were involved early enough (requirements, testing) in the last rollout of ICERTIS/SPM ARIBA affecting me - SPM ARIBA",
        "I understood the “why” (benefits, pain points solved) before go-live - ICERTIS",
        "I understood the “why” (benefits, pain points solved) before go-live - SPM ARIBA",
        "My manager/leadership set clear expectations to use the new system(s) as the single source of record",
        "If you choose \"strongly disagree/disagree\" What blocked that?",
        "The training I received on ICERTIS/ARIBA/ MADR was sufficient and timely - Icertis",
        "The training I received on ICERTIS/ARIBA/ MADR was sufficient and timely - SAP ARIBA",
        "The training I received on ICERTIS/ARIBA/ MADR was sufficient and timely - Mainframe/MADR",
        "For my common tasks, the system feels… - ICETIS",
        "For my common tasks, the system feels… - SPM ARIBA",
        "For my common tasks, the system feels… - Mainframe/MADR",
        "When I’m under time pressure, I can still complete tasks in the system without reverting to old methods.",
        "The information I need (prices, terms, agreements) is accurate and complete where I expect to find it. ",
        "Which would help you most in staying on the “happy path”? (Pick two) \n \n ",
        "If you could change one thing in the workflow tomorrow, what would it be and why?"
    ]
    data = [
        [1, "11/7/25 22:26:03", "11/7/25 22:28:12", "anonymous", np.nan, np.nan, "Commodity Manager", "Corporate Bellevue", "Icertis;GPPS/SAP;ARIBA;Mainframe/MADR;", "Strongly disagree", "Disagree", "Disagree", "Disagree", "Strongly agree", "Instructions were unclear;Value not proven;Training Gaps;", "Strongly agree", "Agree", "Agree", "Very Cumbersome", "Neither Cumbersome nor Easy", "Very Cumbersome", "Strongly agree", "Agree", "Task-based micro video;Office Hours;", "User friendly systems"],
        [2, "11/10/25 10:36:09", "11/10/25 10:42:43", "anonymous", np.nan, np.nan, "Commodity Manager", "Corporate Bellevue", "GPPS/SAP;", "Strongly disagree", "Strongly disagree", "Strongly disagree", "Strongly disagree", "Strongly disagree", "Instructions were unclear;Value not proven;Training Gaps;Speed;", "Strongly disagree", "Disagree", "Disagree", "Very Cumbersome", "Very Cumbersome", "Very Cumbersome", "Disagree", "Disagree", "1:1 Coaching;Faster screens/ fewer checks;", "The approval process is taking longer than expected, which is not in accordance with the established procedures and the urgency required. Delays in this process may lead to setbacks in other areas, affecting timely delivery and project schedules."],
        [3, "11/10/25 10:38:56", "11/10/25 10:46:33", "anonymous", np.nan, np.nan, "Commodity Manager", "Corporate Bellevue", "GPPS/SAP;", "Strongly disagree", "Strongly disagree", "Agree", "Disagree", "Disagree", "Instructions were unclear;", "Neither agree nor disagree", "Disagree", "Disagree", "Somewhat Cumebersome", "Somewhat Cumebersome", "Somewhat Cumebersome", "Neither agree nor disagree", "Neutral", "Faster screens/ fewer checks;Better search/reporting;", np.nan]
    ]
    df = pd.DataFrame(data, columns=columns)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='SurveyData')
    return output.getvalue()


@st.cache_data
def load_and_clean_data(file_input):
    """
    Loads, renames, and preprocesses the survey data.
    'file_input' can be an uploaded file object OR a string filepath.
    """
    df = None
    
    # --- NEW: Handle both string paths and file objects ---
    file_name = ""
    if isinstance(file_input, str):
        file_name = file_input
    else:
        # It's an uploaded file object
        file_name = file_input.name
    # --- END NEW ---

    try:
        if file_name.endswith('.csv'):
            df = pd.read_csv(file_input)
        elif file_name.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(file_input)
        else:
            st.error("Unsupported file type. Please upload a CSV or XLSX file.")
            return None
    except FileNotFoundError:
        # This will catch the error if the local file isn't found
        st.error(f"Error: Local file not found. Make sure **{file_name}** is in the same directory as the app.")
        return None
    except Exception as e:
        st.error(f"Error reading file: {e}. Ensure the file is not corrupted.")
        return None

    if df is not None:
        # 1. Rename columns based on the mapping
        inverted_map = {v: k for k, v in COLUMN_MAPPING.items()}
        df = df.rename(columns=inverted_map)

        # 2. Get only the columns we've defined
        defined_cols = list(COLUMN_MAPPING.keys())
        missing_cols = [col for col in defined_cols if col not in df.columns]
        if any(col.startswith('Q') for col in missing_cols):
             st.warning(f"Warning: Your file seems to be missing some expected data columns. The app may not work correctly. Missing: {', '.join(missing_cols)}")
        
        df = df[[col for col in defined_cols if col in df.columns]]

        # 3. Clean multi-select "explode" columns
        for col in ['Q3_Systems', 'Q6_1_Blockers', 'Q14_HelpMost']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip().str.rstrip(';')
        
        return df
    return None

def melt_usability_data(df):
    """Melts the Q8 usability data into a long format for plotting."""
    usability_cols = [col for col in df.columns if col.startswith('Q8_Usability_')]
    if not usability_cols: return pd.DataFrame(columns=['Respondent', 'System', 'Rating'])
    df_usability = df[usability_cols].reset_index().rename(columns={'index': 'Respondent'})
    df_melted = df_usability.melt(id_vars=['Respondent'], value_vars=usability_cols, var_name='System', value_name='Rating')
    df_melted['System'] = df_melted['System'].str.replace('Q8_Usability_', '')
    return df_melted

def plot_likert_chart(df, col_name, title, order):
    """Creates a colored Likert bar chart."""
    if col_name not in df.columns:
        st.warning(f"Chart skipped: Column for '{title}' not found. Check `COLUMN_MAPPING`.")
        return
    color_scale = alt.Scale(domain=LIKERT_ORDER, range=["#d6604d", "#f4a582", "#e0e0e0", "#e0e0e0", "#92c5de", "#4393c3"])
    chart = alt.Chart(df).mark_bar().encode(
        x=alt.X(col_name, title="Response", sort=order, axis=alt.Axis(labels=False)), 
        y=alt.Y('count()', title="Count of Responses"),
        color=alt.Color(col_name, title="Response", scale=color_scale, legend=alt.Legend(orient="bottom", columns=3, titleOrient="top")),
        tooltip=[col_name, 'count()']
    ).properties(title=title).interactive()
    st.altair_chart(chart, use_container_width=True)

def plot_bar_chart(df, col_name, title, is_multi_select=False):
    """Creates a bar chart with readable horizontal labels."""
    if col_name not in df.columns:
        st.warning(f"Chart skipped: Column for '{title}' not found. Check `COLUMN_MAPPING`.")
        return
    if is_multi_select:
        chart_data = df[col_name].dropna().str.split(';').explode().str.strip()
        chart_data = chart_data[chart_data.notna() & (chart_data != '')]
        chart_data_df = chart_data.to_frame(name='Response')
        chart = alt.Chart(chart_data_df).mark_bar().encode(
            x=alt.X('count()', title="Count"),
            y=alt.Y('Response', title="Response", sort='-x', axis=alt.Axis(labelLimit=0)),
            tooltip=['Response', 'count()']
        ).properties(title=title).interactive()
    else:
        chart = alt.Chart(df).mark_bar().encode(
            x=alt.X('count()', title="Count"),
            y=alt.Y(col_name, title="Response", sort='-x', axis=alt.Axis(labelLimit=0)), 
            tooltip=[col_name, 'count()']
        ).properties(title=title).interactive()
    st.altair_chart(chart, use_container_width=True)


# --- NEW: Sentiment Analysis Functions ---
@st.cache_resource
def get_sentiment_analyzer():
    """Initializes the VADER sentiment analyzer."""
    # This prevents re-loading the model on every script run
    return SentimentIntensityAnalyzer()

def get_sentiment(text, analyzer):
    """Returns the compound sentiment score for a block of text."""
    if pd.isna(text) or text.strip() == "":
        return 0.0
    return analyzer.polarity_scores(str(text))['compound']

def categorize_sentiment(score):
    """Categorizes a VADER compound score."""
    if score >= 0.05:
        return 'Positive'
    elif score <= -0.05:
        return 'Negative'
    else:
        return 'Neutral'
# --- END NEW ---

# --- UPDATED: Text Analysis Functions ---
def analyze_themes(feedback_df):
    """Scans feedback text for keywords and tags each comment with themes."""
    theme_df = feedback_df[['Q15_OpenText']].copy()
    theme_tags_list = []
    
    for comment in theme_df['Q15_OpenText']:
        comment_themes = []
        comment_lower = str(comment).lower()
        for theme, keywords in THEME_KEYWORDS.items():
            if any(keyword in comment_lower for keyword in keywords):
                comment_themes.append(theme)
        if not comment_themes:
            theme_tags_list.append('Other/Uncategorized')
        else:
            theme_tags_list.append(', '.join(comment_themes))
            
    theme_df['Themes'] = theme_tags_list
    theme_analysis = theme_df['Themes'].str.split(', ').explode().value_counts().reset_index()
    theme_analysis.columns = ['Theme', 'Count']
    return theme_analysis, feedback_df.merge(theme_df['Themes'], left_index=True, right_index=True)

@st.cache_data
def generate_wordcloud(feedback_df):
    """Generates a word cloud image from the open text feedback."""
    text = " ".join(str(comment) for comment in feedback_df['Q15_OpenText'].dropna())
    if not text: return None
    custom_stopwords = set(STOPWORDS)
    custom_stopwords.update(['system', 'systems', 'icertis', 'ariba', 'madr', 'use', 'using', 'would', 'like', 'one', 'thing'])
    wordcloud = WordCloud(
        stopwords=custom_stopwords, background_color="white",
        width=800, height=400, colormap='viridis', max_words=50
    ).generate(text)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.imshow(wordcloud, interpolation='bilinear')
    ax.axis("off")
    return fig

def build_dashboard(df):
    """Renders the entire Streamlit dashboard with interpretation pointers."""
    
    st.sidebar.title("Survey Filters")
    st.sidebar.markdown("Filter the data by role or division.")
    roles = df['Q1_Role'].unique()
    selected_role = st.sidebar.multiselect("Filter by Role:", roles, default=roles)
    divisions = df['Q2_Division'].unique()
    selected_division = st.sidebar.multiselect("Filter by Division:", divisions, default=divisions)
    filtered_df = df[(df['Q1_Role'].isin(selected_role)) & (df['Q2_Division'].isin(selected_division))]
    
    if filtered_df.empty:
        st.error("No data matches your filter selection.")
        return

    st.sidebar.info(f"Showing **{len(filtered_df)}** of **{len(df)}** responses.")

    # --- NEW: Sidebar Navigation ---
    st.sidebar.divider()
    st.sidebar.title("App Navigation")
    page = st.sidebar.radio(
        "Go to analysis:",
        [
            "📊 H1/H4: Involvement & Governance", 
            "H2: Friction", 
            "🔗 H3: Integrity", 
            "💡 Fixes", 
            "💬 Open Text Analysis"
        ],
        label_visibility="hidden" # Hides the "Go to analysis:" label for a cleaner look
    )
    st.sidebar.divider()
    # --- END NEW ---


    # --- MODIFIED: Replaced 'with tab1:' with 'if page == ...' ---
    if page == "📊 H1/H4: Involvement & Governance":
        st.header("Hypothesis 1 (Involvement) & 4 (Governance)")
        st.markdown("*(H1): Uneven end-user participation... led to... higher workarounds.*")
        st.markdown("*(H4): “Single source of record” is not consistently mandated...*")
        st.subheader("Q4: I was involved early enough")
        col1, col2 = st.columns(2)
        with col1: plot_likert_chart(filtered_df, 'Q4_Involvement_Icertis', "Involvement - ICERTIS", LIKERT_ORDER)
        with col2: plot_likert_chart(filtered_df, 'Q4_Involvement_Ariba', "Involvement - SPM ARIBA", LIKERT_ORDER)
        st.subheader("Q5: I understood the 'why' (benefits)")
        col1, col2 = st.columns(2)
        with col1: plot_likert_chart(filtered_df, 'Q5_Why_Icertis', "Understood 'Why' - ICERTIS", LIKERT_ORDER)
        with col2: plot_likert_chart(filtered_df, 'Q5_Why_Ariba', "Understood 'Why' - SPM ARIBA", LIKERT_ORDER)
        with st.expander("💡 How to Interpret These Charts (H1)"):
            st.markdown("""
            **This is the core of H1 (Involvement).**
            - **Look for Red:** A high number of "Strongly disagree" (red) bars means users felt completely left out of the rollout (Q4) and have no "buy-in" because they don't understand the benefits (Q5).
            - **Compare Systems:** Are users more negative about one system than another? This helps you pinpoint where the change management failed most.
            """)
        st.divider()
        st.subheader("Q6: My manager set clear expectations")
        plot_likert_chart(filtered_df, 'Q6_Mandate', "Q6: My manager set clear expectations (H4)", LIKERT_ORDER)
        with st.expander("💡 How to Interpret This Chart (H4)"):
            st.markdown("""
            **This chart directly tests H4 (Governance).**
            - **Look for Red:** "Disagree" (red) here means the "single source of record" mandate is failing on the front lines.
            - **Filter by Division:** Use the sidebar filters. Does the chart look different for "Corporate" vs. "Other"? If so, you've proven that the mandate (H4) is not being "operationalized consistently across divisions."
            """)
        st.subheader("Analysis: Q6 Blockers")
        st.markdown("What blocked the mandate? (Filtered by those who disagreed with Q6)")
        disagree_q6 = ['Strongly disagree', 'Disagree']
        blocker_df = filtered_df[filtered_df['Q6_Mandate'].isin(disagree_q6)]
        if blocker_df.empty:
            st.info("No 'Disagree' or 'Strongly Disagree' responses for Q6 in the filtered data.")
        else:
            plot_bar_chart(blocker_df, 'Q6_1_Blockers', "What blocked that? (for Q6 dissenters)", is_multi_select=True)
            st.metric("Evidence for H1/H4", f"{len(blocker_df)} / {len(filtered_df[filtered_df['Q6_Mandate'].notna()])} respondents", "disagreed with the mandate.")
        with st.expander("💡 How to Interpret This Chart (The 'Why')"):
            st.markdown("""
            **This is your "smoking gun" chart.**
            - **Look at the Top Bar:** This is the #1 reason for resistance. If you see "Value not proven," it's a direct link to Q5 (users don't know the "why"). If you see "Training Gaps," it's a direct link to H2 (Friction).
            - **This proves H1:** Users who weren't involved (Q4) don't see the value (Q5), so they resist the mandate (Q6) and blame "Value not proven" and "Training" (Blockers).
            """)

    # --- MODIFIED: Replaced 'with tab2:' with 'elif page == ...' ---
    elif page == "H2: Friction":
        st.header("Hypothesis 2: Usability & Training Friction")
        st.markdown("*(H2): Usability/training friction... explains many 'happy-path' deviations.*")
        st.subheader("Q7: Training was sufficient & timely")
        col1, col2, col3 = st.columns(3)
        with col1: plot_likert_chart(filtered_df, 'Q7_Training_Icertis', "Training - ICERTIS", LIKERT_ORDER)
        with col2: plot_likert_chart(filtered_df, 'Q7_Training_Ariba', "Training - SAP ARIBA", LIKERT_ORDER)
        with col3: plot_likert_chart(filtered_df, 'Q7_Training_Mainframe', "Training - Mainframe/MADR", LIKERT_ORDER)
        with st.expander("💡 How to Interpret This Chart (Training Friction)"):
            st.markdown("""**This chart measures "Training Friction."** A lot of "Disagree" (red) confirms users feel the training was poor or non-existent. This is a key part of H2.""")
        st.divider()
        st.subheader("Q8: System Usability ('Feels...')")
        usability_df = melt_usability_data(filtered_df)
        if usability_df.empty:
            st.warning("No 'Q8_Usability_...' columns found. Check `COLUMN_MAPPING`.")
        else:
            usability_chart = alt.Chart(usability_df).mark_bar().encode(
                x=alt.X('Rating', sort=USABILITY_ORDER, axis=alt.Axis(labels=False)),
                y=alt.Y('count()'),
                color=alt.Color('Rating', scale=alt.Scale(domain=USABILITY_ORDER, range=["#d6604d", "#f4a582", "#e0e0e0", "#92c5de", "#4393c3"]), legend=alt.Legend(orient="bottom", columns=3, titleOrient="top")),
                column=alt.Column('System', header=alt.Header(titleOrient="bottom", labelOrient="bottom")),
                tooltip=['System', 'Rating', 'count()']
            ).properties(title="Q8: For my common tasks, the system feels...").interactive()
            st.altair_chart(usability_chart, use_container_width=True)
        with st.expander("💡 How to Interpret This Chart (Usability Friction)"):
            st.markdown("""**This chart measures "Usability Friction."** A lot of "Very Cumbersome" (red) is a major finding. This shows *which system* is causing the most user pain.""")
        st.divider()
        st.subheader("Q9: I can complete tasks under pressure")
        plot_likert_chart(filtered_df, 'Q9_TimePressure', "Q9: I can still complete tasks under pressure", LIKERT_ORDER)
        with st.expander("💡 How to Interpret This Chart (The 'Payoff' for H2)"):
            st.markdown("""
            **This is the payoff chart for H2.** It measures "happy-path deviations."
            - **Look for Red:** "Disagree" (red) here is a direct admission from users that **when they are in a hurry, they give up and revert to old methods.**
            - **The Story:** This chart proves that the "Training Friction" (Q7) and "Usability Friction" (Q8) are not just complaints; they directly lead to workarounds (Q9).
            """)

    # --- MODIFIED: Replaced 'with tab3:' with 'elif page == ...' ---
    elif page == "🔗 H3: Integrity":
        st.header("Hypothesis 3: Data Integrity")
        st.markdown("*(H3): Integration gaps (esp. with legacy) are the primary source of discrepancies.*")
        st.subheader("Q10: Info is accurate and complete (All Users)")
        plot_likert_chart(filtered_df, 'Q10_Accuracy', "Q10: Info is accurate and complete", LIKERT_ORDER)
        st.divider()
        st.subheader("Analysis: Integrity by System (H3 Test)")
        st.markdown("Cross-reference H3 by filtering for users who touch legacy systems.")
        if 'Q3_Systems' in filtered_df.columns:
            mainframe_users = filtered_df[filtered_df['Q3_Systems'].str.contains("Mainframe", na=False)]
            if not mainframe_users.empty:
                st.markdown(f"**Filtering for {len(mainframe_users)} Mainframe User(s):**")
                plot_likert_chart(mainframe_users, 'Q10_Accuracy', "Q10: Info is accurate (Mainframe Users Only)", LIKERT_ORDER)
                with st.expander("💡 How to Interpret This (The H3 Test)"):
                    st.markdown("""
                    **This is your direct test for H3.**
                    - **Compare this chart to the one above ("All Users").**
                    - **Is this chart more red?** If the "Mainframe Users Only" chart is *more negative* than the "All Users" chart, you have strong evidence for H3.
                    - **This proves H3:** It shows that data integrity is a general problem, but it is *acutely* worse for users who touch the legacy Mainframe system.
                    """)
            else:
                st.info("No users in the current filter touch the Mainframe system.")

    # --- MODIFIED: Replaced 'with tab4:' with 'elif page == ...' ---
    elif page == "💡 Fixes":
        st.header("Your Go-Forward Action Plan (Fixes)")
        st.markdown("*(This chart shows what users are asking for to fix H1 and H2)*")
        st.subheader("Q14: What would help you most?")
        plot_bar_chart(filtered_df, 'Q14_HelpMost', "What would help most? (Pick 2)", is_multi_select=True)
        with st.expander("💡 How to Interpret This Chart (Your Action Plan)"):
            st.markdown("""
            **This is your prioritized action plan, as voted by your users.**
            - **Look at the Top 3:** These are the fixes you should prioritize.
            - **Link to Hypotheses:**
                - "Faster screens/fewer checks" -> Fix **H2 (Usability Friction)**.
                - "Task-based micro video" / "1:1 Coaching" -> Fix **H2 (Training Friction)**.
                - "Better search/reporting" -> Fix **H3 (Integrity)**.
            """)

    # --- MODIFIED: Replaced 'with tab5:' with 'elif page == ...' ---
    elif page == "💬 Open Text Analysis":
        st.header("Q15: Open Text Feedback Analysis")
        st.markdown("*(Q15): If you could change one thing in the workflow tomorrow, what would it be and why?*")

        if 'Q15_OpenText' in filtered_df.columns:
            feedback_df = filtered_df[filtered_df['Q15_OpenText'].notna() & (filtered_df['Q15_OpenText'] != 'nan')].copy()
            if feedback_df.empty:
                st.info("No open text feedback in the current selection.")
            else:
                # --- 1. Sentiment Analysis ---
                st.subheader("Overall Feedback Sentiment")
                analyzer = get_sentiment_analyzer()
                feedback_df['Sentiment_Score'] = feedback_df['Q15_OpenText'].apply(lambda x: get_sentiment(x, analyzer))
                feedback_df['Sentiment'] = feedback_df['Sentiment_Score'].apply(categorize_sentiment)
                sentiment_counts = feedback_df['Sentiment'].value_counts().reset_index()
                sentiment_counts.columns = ['Sentiment', 'Count']
                sentiment_chart = alt.Chart(sentiment_counts).mark_bar().encode(
                    x=alt.X('Sentiment', title='Sentiment Category', sort=['Negative', 'Neutral', 'Positive']),
                    y=alt.Y('Count', title='Number of Comments'),
                    color=alt.Color('Sentiment',
                                    scale=alt.Scale(domain=['Negative', 'Neutral', 'Positive'],
                                                    range=['#d6604d', '#e0e0e0', '#4393c3'])),
                    tooltip=['Sentiment', 'Count']
                ).properties(title="Overall Sentiment of Open Feedback").interactive()
                st.altair_chart(sentiment_chart, use_container_width=True)
                with st.expander("💡 How to Interpret This Chart"):
                    st.markdown("""
                    This chart shows the overall "mood" of your users' free-text comments.
                    - **Look for Red:** A large "Negative" bar confirms that the friction seen in the other tabs is translating to genuine frustration.
                    - **This adds context:** You can now say, "Not only do the charts show frustration, but the sentiment of the written feedback is also X% negative."
                    """)

                # --- 2. Automated Theme Analysis ---
                st.divider()
                st.subheader("Top Feedback Themes")
                st.markdown("Comments are automatically scanned for keywords related to your hypotheses.")
                theme_counts, feedback_with_themes = analyze_themes(feedback_df)
                theme_chart = alt.Chart(theme_counts).mark_bar().encode(
                    x=alt.X('Count', title='Number of Comments'),
                    y=alt.Y('Theme', title='Feedback Theme', sort='-x', axis=alt.Axis(labelLimit=0)),
                    tooltip=['Theme', 'Count']
                ).properties(title="Top Themes in Open Feedback").interactive()
                st.altair_chart(theme_chart, use_container_width=True)
                with st.expander("💡 How to Interpret This Chart"):
                    st.markdown("""
                    This chart proves *which* of your hypotheses are most important to users.
                    - **Connect this to your other tabs.** If your H2 charts showed high friction, and "H2_Usability_Friction" is the #1 theme here, you have a very powerful, consistent story.
                    - **This is your "Why".** You can now say, "The data shows users are unhappy with usability, and their free-text comments overwhelmingly confirm this is their biggest pain point."
                    """)

                # --- 3. Word Cloud ---
                st.divider()
                st.subheader("Feedback Word Cloud")
                st.markdown("A quick visual of the most frequent (and non-trivial) words used in comments.")
                wordcloud_fig = generate_wordcloud(feedback_with_themes)
                if wordcloud_fig:
                    st.pyplot(wordcloud_fig)
                with st.expander("💡 How to Interpret This Chart"):
                    st.markdown("""
                    The bigger the word, the more often it was mentioned. I have filtered out common words like 'system' or 'Icertis' to get more useful terms.
                    - **Look for action words:** "slow," "faster," "easier," "remove."
                    - **Look for pain points:** "steps," "process," "training."
                    """)

                # --- 4. Full Feedback Table (with themes & sentiment) ---
                st.divider()
                st.subheader("All Feedback (with Automated Analysis)")
                st.dataframe(feedback_with_themes[['Q1_Role', 'Q15_OpenText', 'Themes', 'Sentiment']], use_container_width=True)

        else:
            st.warning("Column 'Q15_OpenText' not found. Check `COLUMN_MAPPING`.")
    # --- END REBUILT TAB 5 ---

# --- Main Application Logic (UPDATED) ---
def main():
    st.set_page_config(layout="wide")
    
    st.subheader("University of Washington Bothell | B BUS 510 (MANAGING ORGANIZATIONAL EFFECTIVENESS)")
    st.title("📊 Group B4: Automated Survey Hypothesis Tester")
    st.markdown("---") 
    
    st.markdown("Upload your survey file, or download the template to see the required format.")

    try:
        template_excel = create_template_excel()
        st.download_button(
            label="📥 Download Template (.xlsx)",
            data=template_excel,
            file_name="survey_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            help="Click to download an Excel file with the required headers and 3 sample data rows."
        )
    except Exception as e:
        st.error(f"Error creating template file: {e}")

    st.divider() 

    # --- NEW: Initialize Session State & Auto-Load ---
    if 'data' not in st.session_state:
        st.session_state.data = None
        
        # Check for local file immediately on startup
        local_file_name = "College Case study Survey.xlsx"
        if os.path.exists(local_file_name):
            try:
                auto_loaded_data = load_and_clean_data(local_file_name)
                if auto_loaded_data is not None:
                    st.session_state.data = auto_loaded_data
                    st.toast(f"✅ Automatically loaded: {local_file_name}") # Nice popup notification
            except Exception as e:
                st.warning(f"Could not auto-load local file: {e}")
    # --- END NEW ---

    # --- Two-column layout for manual overrides ---
    col1, col2 = st.columns(2)

    with col1:
        uploaded_file = st.file_uploader(
            "Option 1: Upload a different file (CSV or XLSX)", 
            type=['csv', 'xlsx']
        )
        if uploaded_file is not None:
            try:
                st.session_state.data = load_and_clean_data(uploaded_file)
                if st.session_state.data is not None:
                    st.success(f"Successfully loaded **{uploaded_file.name}**.")
            except Exception as e:
                st.error(f"An error occurred: {e}")
                st.session_state.data = None

    with col2:
        st.markdown("Option 2: Reload the local project file")
        local_file_name = "College Case study Survey.xlsx"
        
        # We disable the button if the file doesn't exist, for clarity
        file_exists = os.path.exists(local_file_name)
        if st.button(f"Reload Local File: `{local_file_name}`", disabled=not file_exists):
            try:
                st.session_state.data = load_and_clean_data(local_file_name)
                if st.session_state.data is not None:
                    st.success(f"Successfully loaded **{local_file_name}**.")
            except Exception as e:
                st.session_state.data = None
    
    st.divider()

    # --- Run the dashboard ---
    if st.session_state.data is not None:
        build_dashboard(st.session_state.data)
    else:
        st.info("Awaiting your survey file... (Upload a file or ensure 'College Case study Survey.xlsx' is in the folder)")

if __name__ == "__main__":
    main()