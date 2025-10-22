
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import re
from typing import List, Dict, Tuple
import json

# Page configuration
st.set_page_config(
    page_title="RUN-InnoBoost Mentor Matching System",
    page_icon="🤝",
    layout="wide"
)

# Initialize session state for data persistence
if 'mentors' not in st.session_state:
    st.session_state.mentors = pd.DataFrame(columns=[
        'MentorID', 'Name', 'Email', 'Institution', 'Role/Title', 'City', 
        'Country', 'TimeZone', 'Gender', 'Languages', 'Sectors', 
        'Expertise', 'Functions', 'Seniority', 'MaxMentees', 
        'Availability', 'Format', 'LinkedIn', 'Conflicts', 'Notes'
    ])

if 'mentees' not in st.session_state:
    st.session_state.mentees = pd.DataFrame(columns=[
        'MenteeID', 'Name', 'Email', 'Institution', 'LPOC', 'ParticipantType',
        'ProjectName', 'Stage', 'Sector', 'Needs', 'TopDecision', 
        'Goals', 'Languages', 'City', 'Country', 'TimeZone', 
        'Availability', 'Format', 'Brief', 'Gender', 'Consent', 'Notes'
    ])

if 'matches' not in st.session_state:
    st.session_state.matches = pd.DataFrame(columns=[
        'MatchID', 'MenteeID', 'MentorID', 'Status', 'PriorityScore', 
        'Rationale', 'StartDate', 'Session1', 'Session2', 'Session3',
        'MenteeSatisfaction', 'MentorSatisfaction', 'Outcome', 
        'ConvertedToMentor', 'ClosedDate', 'LPOC'
    ])

# Matching Algorithm Functions
def calculate_tag_overlap(tags1: str, tags2: str) -> float:
    """Calculate percentage overlap between two comma-separated tag strings"""
    if pd.isna(tags1) or pd.isna(tags2) or not tags1 or not tags2:
        return 0.0

    set1 = set([t.strip().lower() for t in str(tags1).split(',')])
    set2 = set([t.strip().lower() for t in str(tags2).split(',')])

    if not set1 or not set2:
        return 0.0

    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))

    return (intersection / union) * 100 if union > 0 else 0.0

def check_language_match(mentor_langs: str, mentee_langs: str) -> bool:
    """Check if mentor and mentee share at least one common language"""
    if pd.isna(mentor_langs) or pd.isna(mentee_langs):
        return False

    mentor_set = set([l.strip().lower() for l in str(mentor_langs).split(',')])
    mentee_set = set([l.strip().lower() for l in str(mentee_langs).split(',')])

    return len(mentor_set.intersection(mentee_set)) > 0

def check_format_compatibility(mentor_format: str, mentee_format: str) -> bool:
    """Check if meeting format preferences are compatible"""
    if pd.isna(mentor_format) or pd.isna(mentee_format):
        return True  # Default to compatible if not specified

    mentor_fmt = str(mentor_format).strip().lower()
    mentee_fmt = str(mentee_format).strip().lower()

    if 'either' in mentor_fmt or 'either' in mentee_fmt:
        return True

    return mentor_fmt == mentee_fmt

def check_timezone_compatibility(mentor_tz: str, mentee_tz: str) -> bool:
    """Check if timezones allow for reasonable meeting times"""
    if pd.isna(mentor_tz) or pd.isna(mentee_tz):
        return True

    # Simplified - in production, use actual timezone offset calculation
    return str(mentor_tz).strip().lower() == str(mentee_tz).strip().lower()

def calculate_match_score(mentor_row: pd.Series, mentee_row: pd.Series) -> Tuple[float, str]:
    """
    Calculate compatibility score (0-100) and rationale between mentor and mentee
    """
    score_components = {}
    rationale_parts = []

    # 1. Sector/Expertise overlap (30% weight)
    sector_overlap = calculate_tag_overlap(mentor_row['Sectors'], mentee_row['Sector'])
    expertise_overlap = calculate_tag_overlap(mentor_row['Expertise'], mentee_row['Needs'])

    sector_score = (sector_overlap * 0.4 + expertise_overlap * 0.6)
    score_components['sector_expertise'] = sector_score * 0.30

    if sector_overlap > 50:
        rationale_parts.append(f"Strong sector alignment ({sector_overlap:.0f}%)")
    if expertise_overlap > 50:
        rationale_parts.append(f"High expertise-needs match ({expertise_overlap:.0f}%)")

    # 2. Language compatibility (20% weight)
    has_language_match = check_language_match(mentor_row['Languages'], mentee_row['Languages'])
    language_score = 100 if has_language_match else 0
    score_components['language'] = language_score * 0.20

    if has_language_match:
        rationale_parts.append("Common language")
    else:
        rationale_parts.append("⚠️ No language overlap")

    # 3. Format compatibility (15% weight)
    format_compatible = check_format_compatibility(mentor_row['Format'], mentee_row['Format'])
    format_score = 100 if format_compatible else 30
    score_components['format'] = format_score * 0.15

    if format_compatible:
        rationale_parts.append("Format compatible")

    # 4. Timezone compatibility (10% weight)
    timezone_compatible = check_timezone_compatibility(mentor_row['TimeZone'], mentee_row['TimeZone'])
    timezone_score = 100 if timezone_compatible else 50
    score_components['timezone'] = timezone_score * 0.10

    if timezone_compatible:
        rationale_parts.append("Same timezone")

    # 5. Availability overlap (15% weight)
    availability_score = 100 if not pd.isna(mentor_row['Availability']) and not pd.isna(mentee_row['Availability']) else 50
    score_components['availability'] = availability_score * 0.15

    # 6. Functional expertise (10% weight)
    function_overlap = calculate_tag_overlap(mentor_row['Functions'], mentee_row['Needs'])
    score_components['functions'] = function_overlap * 0.10

    if function_overlap > 40:
        rationale_parts.append(f"Functional fit ({function_overlap:.0f}%)")

    # Calculate total score
    total_score = sum(score_components.values())

    # Build rationale string
    rationale = "; ".join(rationale_parts)

    return round(total_score, 1), rationale

def find_best_matches(mentors_df: pd.DataFrame, mentees_df: pd.DataFrame, top_n: int = 3) -> pd.DataFrame:
    """
    Find best mentor matches for all mentees
    """
    all_matches = []

    for _, mentee in mentees_df.iterrows():
        mentee_matches = []

        for _, mentor in mentors_df.iterrows():
            score, rationale = calculate_match_score(mentor, mentee)

            mentee_matches.append({
                'MenteeID': mentee['MenteeID'],
                'MenteeName': mentee['Name'],
                'MentorID': mentor['MentorID'],
                'MentorName': mentor['Name'],
                'Score': score,
                'Rationale': rationale,
                'MentorEmail': mentor['Email'],
                'MenteeEmail': mentee['Email']
            })

        # Sort by score and take top N
        mentee_matches.sort(key=lambda x: x['Score'], reverse=True)
        all_matches.extend(mentee_matches[:top_n])

    return pd.DataFrame(all_matches)

# Application Header
st.title("🤝 RUN-InnoBoost Mentor Matching System")
st.markdown("**Intelligent mentor-mentee matching powered by algorithmic scoring**")

# Sidebar Navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", [
    "🏠 Dashboard",
    "👨‍🏫 Manage Mentors",
    "👨‍🎓 Manage Mentees",
    "🎯 Smart Matching",
    "📊 Match Management",
    "📤 Export Data"
])

# ==================== DASHBOARD PAGE ====================
if page == "🏠 Dashboard":
    st.header("Dashboard Overview")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Mentors", len(st.session_state.mentors))
    with col2:
        st.metric("Total Mentees", len(st.session_state.mentees))
    with col3:
        st.metric("Active Matches", 
                 len(st.session_state.matches[st.session_state.matches['Status'] == 'Active']) 
                 if len(st.session_state.matches) > 0 else 0)
    with col4:
        avg_score = st.session_state.matches['PriorityScore'].mean() if len(st.session_state.matches) > 0 else 0
        st.metric("Avg Match Score", f"{avg_score:.1f}")

    st.subheader("Quick Stats")

    if len(st.session_state.mentors) > 0:
        st.write("**Top Mentor Sectors:**")
        all_sectors = []
        for sectors in st.session_state.mentors['Sectors'].dropna():
            all_sectors.extend([s.strip() for s in str(sectors).split(',')])
        if all_sectors:
            sector_counts = pd.Series(all_sectors).value_counts().head(5)
            st.bar_chart(sector_counts)

    if len(st.session_state.mentees) > 0:
        st.write("**Mentee Project Stages:**")
        stage_counts = st.session_state.mentees['Stage'].value_counts()
        st.bar_chart(stage_counts)

# ==================== MANAGE MENTORS PAGE ====================
elif page == "👨‍🏫 Manage Mentors":
    st.header("Mentor Management")

    tab1, tab2, tab3 = st.tabs(["➕ Add Mentor", "📋 View All", "📥 Bulk Import"])

    with tab1:
        st.subheader("Add New Mentor")

        with st.form("add_mentor_form"):
            col1, col2 = st.columns(2)

            with col1:
                mentor_id = st.text_input("Mentor ID*", 
                                         value=f"M{len(st.session_state.mentors)+1:03d}")
                name = st.text_input("Full Name*")
                email = st.text_input("Email*")
                institution = st.text_input("Institution")
                role = st.text_input("Role/Title")
                city = st.text_input("City")
                country = st.text_input("Country")
                timezone = st.text_input("Timezone (e.g., UTC+1)")
                gender = st.text_input("Gender (optional)")
                languages = st.text_input("Languages (comma-separated)*", 
                                         placeholder="English, Portuguese, Spanish")

            with col2:
                sectors = st.text_input("Sectors (comma-separated)*",
                                       placeholder="FinTech, HealthTech, EdTech")
                expertise = st.text_input("Expertise/Topics (comma-separated)*",
                                         placeholder="Product Development, Marketing, Fundraising")
                functions = st.text_input("Functions (comma-separated)",
                                         placeholder="Strategy, Operations, Finance")
                seniority = st.selectbox("Seniority Level", 
                                        ["Junior", "Mid", "Senior", "C-Level", "Founder"])
                max_mentees = st.number_input("Max Concurrent Mentees", min_value=1, max_value=10, value=3)
                availability = st.text_input("Availability (next 6 weeks)")
                format_pref = st.selectbox("Meeting Format", ["Remote", "In-person", "Either"])
                linkedin = st.text_input("LinkedIn/Website")
                conflicts = st.text_input("Conflicts (Y/N + notes)")
                notes = st.text_area("Additional Notes")

            submitted = st.form_submit_button("Add Mentor")

            if submitted:
                if name and email and languages:
                    new_mentor = pd.DataFrame([{
                        'MentorID': mentor_id,
                        'Name': name,
                        'Email': email,
                        'Institution': institution,
                        'Role/Title': role,
                        'City': city,
                        'Country': country,
                        'TimeZone': timezone,
                        'Gender': gender,
                        'Languages': languages,
                        'Sectors': sectors,
                        'Expertise': expertise,
                        'Functions': functions,
                        'Seniority': seniority,
                        'MaxMentees': max_mentees,
                        'Availability': availability,
                        'Format': format_pref,
                        'LinkedIn': linkedin,
                        'Conflicts': conflicts,
                        'Notes': notes
                    }])

                    st.session_state.mentors = pd.concat([st.session_state.mentors, new_mentor], 
                                                         ignore_index=True)
                    st.success(f"✅ Mentor {name} added successfully!")
                    st.rerun()
                else:
                    st.error("Please fill all required fields (*)")

    with tab2:
        st.subheader("All Mentors")

        if len(st.session_state.mentors) > 0:
            # Display simplified view
            display_cols = ['MentorID', 'Name', 'Email', 'Institution', 'Sectors', 
                          'Expertise', 'Languages', 'Format']
            st.dataframe(st.session_state.mentors[display_cols], use_container_width=True)

            # Delete option
            mentor_to_delete = st.selectbox("Select mentor to delete", 
                                           st.session_state.mentors['MentorID'].tolist(),
                                           key="delete_mentor_select")
            if st.button("🗑️ Delete Selected Mentor"):
                st.session_state.mentors = st.session_state.mentors[
                    st.session_state.mentors['MentorID'] != mentor_to_delete
                ]
                st.success("Mentor deleted!")
                st.rerun()
        else:
            st.info("No mentors added yet. Add your first mentor in the 'Add Mentor' tab.")

    with tab3:
        st.subheader("Bulk Import Mentors")
        st.markdown("Upload a CSV file with mentor data. [Download template](#)")

        uploaded_file = st.file_uploader("Choose CSV file", type=['csv'])
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file)
                st.write("Preview:")
                st.dataframe(df.head())

                if st.button("Import All Mentors"):
                    st.session_state.mentors = pd.concat([st.session_state.mentors, df], 
                                                         ignore_index=True)
                    st.success(f"✅ Imported {len(df)} mentors successfully!")
                    st.rerun()
            except Exception as e:
                st.error(f"Error reading file: {e}")

# ==================== MANAGE MENTEES PAGE ====================
elif page == "👨‍🎓 Manage Mentees":
    st.header("Mentee Management")

    tab1, tab2, tab3 = st.tabs(["➕ Add Mentee", "📋 View All", "📥 Bulk Import"])

    with tab1:
        st.subheader("Add New Mentee")

        with st.form("add_mentee_form"):
            col1, col2 = st.columns(2)

            with col1:
                mentee_id = st.text_input("Mentee ID*", 
                                         value=f"ME{len(st.session_state.mentees)+1:03d}")
                name = st.text_input("Name/Team Lead*")
                email = st.text_input("Email*")
                institution = st.text_input("Institution")
                lpoc = st.text_input("LPOC (Local Point of Contact)")
                participant_type = st.selectbox("Participant Type", 
                                               ["student", "researcher", "staff"])
                project_name = st.text_input("Project/Challenge Name*")
                stage = st.selectbox("Project Stage", 
                                    ["idea", "prototype", "MVP", "early startup", "scale-up", "other"])
                sector = st.text_input("Sector (comma-separated)*",
                                      placeholder="FinTech, AI, SaaS")
                needs = st.text_input("Needs/Topics (comma-separated)*",
                                     placeholder="Go-to-market, Fundraising, Product-market fit")
                top_decision = st.text_input("Top Decision (30-60 days)")

            with col2:
                goals = st.text_area("Goals (bullets)")
                languages = st.text_input("Preferred Language(s)*",
                                         placeholder="English, Portuguese")
                city = st.text_input("City")
                country = st.text_input("Country")
                timezone = st.text_input("Timezone")
                availability = st.text_input("Availability (next 6 weeks)")
                format_pref = st.selectbox("Meeting Format Preference", 
                                          ["Remote", "In-person", "Either"])
                brief_link = st.text_input("Link to Project Brief")
                gender = st.text_input("Gender (optional)")
                consent = st.selectbox("Consent Given", ["Y", "N"])
                notes = st.text_area("Additional Notes")

            submitted = st.form_submit_button("Add Mentee")

            if submitted:
                if name and email and project_name and sector and needs and languages:
                    new_mentee = pd.DataFrame([{
                        'MenteeID': mentee_id,
                        'Name': name,
                        'Email': email,
                        'Institution': institution,
                        'LPOC': lpoc,
                        'ParticipantType': participant_type,
                        'ProjectName': project_name,
                        'Stage': stage,
                        'Sector': sector,
                        'Needs': needs,
                        'TopDecision': top_decision,
                        'Goals': goals,
                        'Languages': languages,
                        'City': city,
                        'Country': country,
                        'TimeZone': timezone,
                        'Availability': availability,
                        'Format': format_pref,
                        'Brief': brief_link,
                        'Gender': gender,
                        'Consent': consent,
                        'Notes': notes
                    }])

                    st.session_state.mentees = pd.concat([st.session_state.mentees, new_mentee], 
                                                         ignore_index=True)
                    st.success(f"✅ Mentee {name} added successfully!")
                    st.rerun()
                else:
                    st.error("Please fill all required fields (*)")

    with tab2:
        st.subheader("All Mentees")

        if len(st.session_state.mentees) > 0:
            display_cols = ['MenteeID', 'Name', 'Email', 'ProjectName', 'Stage', 
                          'Sector', 'Needs', 'Languages']
            st.dataframe(st.session_state.mentees[display_cols], use_container_width=True)

            mentee_to_delete = st.selectbox("Select mentee to delete", 
                                           st.session_state.mentees['MenteeID'].tolist(),
                                           key="delete_mentee_select")
            if st.button("🗑️ Delete Selected Mentee"):
                st.session_state.mentees = st.session_state.mentees[
                    st.session_state.mentees['MenteeID'] != mentee_to_delete
                ]
                st.success("Mentee deleted!")
                st.rerun()
        else:
            st.info("No mentees added yet. Add your first mentee in the 'Add Mentee' tab.")

    with tab3:
        st.subheader("Bulk Import Mentees")
        uploaded_file = st.file_uploader("Choose CSV file", type=['csv'], key="mentee_upload")
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file)
                st.write("Preview:")
                st.dataframe(df.head())

                if st.button("Import All Mentees"):
                    st.session_state.mentees = pd.concat([st.session_state.mentees, df], 
                                                         ignore_index=True)
                    st.success(f"✅ Imported {len(df)} mentees successfully!")
                    st.rerun()
            except Exception as e:
                st.error(f"Error reading file: {e}")

# ==================== SMART MATCHING PAGE ====================
elif page == "🎯 Smart Matching":
    st.header("Smart Mentor-Mentee Matching")
    st.markdown("**AI-powered algorithm matches mentees with the best mentors based on multiple criteria**")

    if len(st.session_state.mentors) == 0 or len(st.session_state.mentees) == 0:
        st.warning("⚠️ Please add mentors and mentees before running the matching algorithm.")
    else:
        st.info(f"📊 Ready to match {len(st.session_state.mentees)} mentees with {len(st.session_state.mentors)} mentors")

        col1, col2 = st.columns(2)
        with col1:
            top_n = st.slider("Number of mentor suggestions per mentee", 1, 5, 3)
        with col2:
            min_score = st.slider("Minimum match score threshold", 0, 100, 40)

        if st.button("🚀 Run Matching Algorithm", type="primary"):
            with st.spinner("Calculating optimal matches..."):
                matches_df = find_best_matches(st.session_state.mentors, 
                                               st.session_state.mentees, 
                                               top_n=top_n)

                # Filter by minimum score
                matches_df = matches_df[matches_df['Score'] >= min_score]

                st.success(f"✅ Found {len(matches_df)} potential matches!")

                # Display results grouped by mentee
                st.subheader("Matching Results")

                for mentee_id in matches_df['MenteeID'].unique():
                    mentee_matches = matches_df[matches_df['MenteeID'] == mentee_id].sort_values(
                        'Score', ascending=False
                    )

                    mentee_name = mentee_matches.iloc[0]['MenteeName']

                    with st.expander(f"🎓 {mentee_name} ({mentee_id}) - {len(mentee_matches)} matches", 
                                    expanded=True):

                        for idx, match in mentee_matches.iterrows():
                            col1, col2, col3 = st.columns([3, 1, 2])

                            with col1:
                                st.markdown(f"**👨‍🏫 {match['MentorName']}** ({match['MentorID']})")
                                st.caption(match['Rationale'])

                            with col2:
                                score_color = "🟢" if match['Score'] >= 70 else "🟡" if match['Score'] >= 50 else "🟠"
                                st.metric("Match Score", f"{match['Score']:.1f}", 
                                         delta=None, label_visibility="collapsed")
                                st.caption(f"{score_color}")

                            with col3:
                                if st.button(f"✅ Approve Match", 
                                           key=f"approve_{match['MenteeID']}_{match['MentorID']}"):
                                    # Create match record
                                    new_match = pd.DataFrame([{
                                        'MatchID': f"MA{len(st.session_state.matches)+1:03d}",
                                        'MenteeID': match['MenteeID'],
                                        'MentorID': match['MentorID'],
                                        'Status': 'Proposed',
                                        'PriorityScore': match['Score'],
                                        'Rationale': match['Rationale'],
                                        'StartDate': '',
                                        'Session1': '',
                                        'Session2': '',
                                        'Session3': '',
                                        'MenteeSatisfaction': np.nan,
                                        'MentorSatisfaction': np.nan,
                                        'Outcome': '',
                                        'ConvertedToMentor': '',
                                        'ClosedDate': '',
                                        'LPOC': ''
                                    }])

                                    st.session_state.matches = pd.concat(
                                        [st.session_state.matches, new_match], 
                                        ignore_index=True
                                    )
                                    st.success(f"Match created: {match['MenteeName']} ↔ {match['MentorName']}")
                                    st.rerun()

                            st.divider()

# ==================== MATCH MANAGEMENT PAGE ====================
elif page == "📊 Match Management":
    st.header("Match Management & Tracking")

    if len(st.session_state.matches) == 0:
        st.info("No matches created yet. Go to 'Smart Matching' to create matches.")
    else:
        # Filter options
        col1, col2, col3 = st.columns(3)
        with col1:
            status_filter = st.multiselect("Filter by Status", 
                                          ["Proposed", "Confirmed", "Active", "Completed", "Declined"],
                                          default=["Proposed", "Confirmed", "Active"])

        filtered_matches = st.session_state.matches[
            st.session_state.matches['Status'].isin(status_filter)
        ] if status_filter else st.session_state.matches

        st.subheader(f"All Matches ({len(filtered_matches)})")

        # Display matches
        for idx, match in filtered_matches.iterrows():
            with st.expander(f"Match {match['MatchID']} - Score: {match['PriorityScore']:.1f} - Status: {match['Status']}"):
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("**Mentee:**")
                    st.write(f"ID: {match['MenteeID']}")

                    st.markdown("**Mentor:**")
                    st.write(f"ID: {match['MentorID']}")

                    st.markdown("**Match Details:**")
                    st.write(f"Priority Score: {match['PriorityScore']:.1f}")
                    st.write(f"Rationale: {match['Rationale']}")

                with col2:
                    new_status = st.selectbox("Update Status", 
                                            ["Proposed", "Confirmed", "Active", "Completed", "Declined"],
                                            index=["Proposed", "Confirmed", "Active", "Completed", "Declined"].index(match['Status']),
                                            key=f"status_{idx}")

                    start_date = st.date_input("Start Date", key=f"start_{idx}")
                    session1_date = st.date_input("Session 1 Date", key=f"s1_{idx}")

                    if new_status in ["Completed"]:
                        mentee_sat = st.slider("Mentee Satisfaction", 1, 5, 3, key=f"msat_{idx}")
                        mentor_sat = st.slider("Mentor Satisfaction", 1, 5, 3, key=f"mrsat_{idx}")
                        outcome = st.text_area("Outcome", key=f"outcome_{idx}")

                    if st.button("💾 Update Match", key=f"update_{idx}"):
                        st.session_state.matches.at[idx, 'Status'] = new_status
                        st.session_state.matches.at[idx, 'StartDate'] = str(start_date)
                        st.session_state.matches.at[idx, 'Session1'] = str(session1_date)
                        st.success("Match updated!")
                        st.rerun()

# ==================== EXPORT DATA PAGE ====================
elif page == "📤 Export Data":
    st.header("Export Data")

    st.markdown("Download your mentor, mentee, and match data in various formats.")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("Mentors")
        if len(st.session_state.mentors) > 0:
            csv_mentors = st.session_state.mentors.to_csv(index=False)
            st.download_button("📥 Download Mentors CSV", 
                             csv_mentors, 
                             "mentors.csv", 
                             "text/csv")
        else:
            st.info("No mentor data")

    with col2:
        st.subheader("Mentees")
        if len(st.session_state.mentees) > 0:
            csv_mentees = st.session_state.mentees.to_csv(index=False)
            st.download_button("📥 Download Mentees CSV", 
                             csv_mentees, 
                             "mentees.csv", 
                             "text/csv")
        else:
            st.info("No mentee data")

    with col3:
        st.subheader("Matches")
        if len(st.session_state.matches) > 0:
            csv_matches = st.session_state.matches.to_csv(index=False)
            st.download_button("📥 Download Matches CSV", 
                             csv_matches, 
                             "matches.csv", 
                             "text/csv")
        else:
            st.info("No match data")

    st.divider()

    # Export to Excel (all sheets)
    st.subheader("Complete Export")
    if st.button("📦 Generate Complete Excel Export"):
        from io import BytesIO

        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            st.session_state.mentors.to_excel(writer, sheet_name='Mentors', index=False)
            st.session_state.mentees.to_excel(writer, sheet_name='Mentees', index=False)
            st.session_state.matches.to_excel(writer, sheet_name='Matches', index=False)

        excel_data = output.getvalue()

        st.download_button(
            label="📥 Download Complete Excel File",
            data=excel_data,
            file_name=f"mentor_matching_export_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("**RUN-InnoBoost Matching System v1.0**")
st.sidebar.caption("Powered by intelligent matching algorithms")
