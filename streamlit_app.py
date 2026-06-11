import json
from pathlib import Path
import re

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Course Scheduler", layout="wide")

st.title("Course Scheduler")

MODULE_FOLDER = Path("Module als json")

PLANS_FOLDER = Path("plans")
PLANS_FOLDER.mkdir(exist_ok=True)


def clean_plan_name(name):
    """Create a safe file name from a user-provided plan name."""
    name = name.strip()
    name = re.sub(r"[^a-zA-Z0-9_\- ]", "", name)
    name = name.replace(" ", "_")
    return name


def plan_path(plan_name):
    """Return the JSON path for a named plan."""
    safe_name = clean_plan_name(plan_name)
    return PLANS_FOLDER / f"{safe_name}.json"


def list_saved_plans():
    """List all saved plans without the .json suffix."""
    return sorted(path.stem for path in PLANS_FOLDER.glob("*.json"))


def extract_cp(cp_text):
    """Extract the first CP number from strings such as '6 CP = 180 h'."""
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*CP", str(cp_text))
    if match:
        return float(match.group(1).replace(",", "."))
    return 0.0


def load_plan(plan_name):
    """Load saved semester assignments for a named plan if it exists."""
    path = plan_path(plan_name)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_plan(df, plan_name):
    """Save only the semester assignment, not the full module descriptions."""
    path = plan_path(plan_name)
    plan = dict(zip(df["code"], df["semester"]))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=4, ensure_ascii=False)


# --- Plan deletion function
def delete_plan(plan_name):
    """Delete a named plan if it exists."""
    path = plan_path(plan_name)
    if path.exists():
        path.unlink()


def load_modules():
    """Load all module JSON files and convert them into a scheduler table."""
    plan = load_plan(st.session_state["active_plan"])
    rows = []

    if not MODULE_FOLDER.exists():
        st.error(f"Module folder not found: {MODULE_FOLDER}")
        st.stop()

    for path in sorted(MODULE_FOLDER.glob("*.json")):
        with open(path, "r", encoding="utf-8") as f:
            module = json.load(f)

        code = module.get("Modul-Code", path.stem)
        name_de = module.get("Modul-Name-de", "")
        name_en = module.get("Modul-Name-en", "")
        cp_text = module.get("Anzhal CP und Arbeitsaufwand", "")

        module_type = str(module.get("Modul-Typ", ""))

        if "Wahlpflichtmodul" in module_type:
            default_selected_type = "Wahlpflichtmodul"
        elif "Pflichtmodul" in module_type:
            default_selected_type = "Pflichtmodul"
        else:
            default_selected_type = "Pflichtmodul"

        rows.append({
            "code": code,
            "course": name_de or name_en or code,
            "cp": extract_cp(cp_text),
            "type": module_type,
            "selected_type": default_selected_type,
            "responsible": module.get("Modulbeauftragte / Modulbeauftragter", ""),
            "semester": plan.get(code, "Unplanned"),
            "file": str(path)
        })

    return pd.DataFrame(rows)



# Plan selection UI block
saved_plans = list_saved_plans()

if "active_plan" not in st.session_state:
    st.session_state["active_plan"] = saved_plans[0] if saved_plans else "default"

st.sidebar.header("Plans")

plan_options = saved_plans.copy()

if st.session_state["active_plan"] not in plan_options:
    plan_options.append(st.session_state["active_plan"])

if not plan_options:
    plan_options = ["default"]

plan_options = sorted(plan_options)


selected_plan = st.sidebar.selectbox(
    "Load plan",
    options=plan_options,
    index=plan_options.index(st.session_state["active_plan"])
)

# Update active_plan and rerun if selection changes
if selected_plan != st.session_state["active_plan"]:
    st.session_state["active_plan"] = selected_plan
    st.rerun()


new_plan_name = st.sidebar.text_input("Save as", value=st.session_state["active_plan"])

# --- Sidebar delete UI block
if saved_plans:
    st.sidebar.divider()
    st.sidebar.subheader("Delete plan")
    plan_to_delete = st.sidebar.selectbox("Plan to delete", options=saved_plans)
    confirm_delete = st.sidebar.checkbox(f"Really delete `{plan_to_delete}`?")

    if st.sidebar.button("Delete selected plan", disabled=not confirm_delete):
        delete_plan(plan_to_delete)
        remaining_plans = list_saved_plans()
        st.session_state["active_plan"] = remaining_plans[0] if remaining_plans else "default"
        st.sidebar.success(f"Deleted plan `{plan_to_delete}`")
        st.rerun()


courses = load_modules()

edited = st.data_editor(
    courses,
    column_config={
        "code": st.column_config.TextColumn("Code"),
        "course": st.column_config.TextColumn("Course"),
        "cp": st.column_config.NumberColumn("CP", format="%d"),
        "type": st.column_config.TextColumn("Type"),
        "selected_type": st.column_config.SelectboxColumn(
            "Selected type",
            options=["Pflichtmodul", "Wahlpflichtmodul"]
        ),
        "responsible": st.column_config.TextColumn("Responsible"),
        "semester": st.column_config.SelectboxColumn(
            "Semester",
            options=["Unplanned", "Semester 1", "Semester 2", "Semester 3", "Semester 4", "Semester 5", "Semester 6"]
        ),
        "file": st.column_config.TextColumn("File")
    },
    disabled=["code", "course", "cp", "type", "responsible", "file"],
    hide_index=True,
    use_container_width=True
)


# --- Save plan block with overwrite warning and confirmation
safe_name = clean_plan_name(new_plan_name)
plan_will_overwrite = (
    safe_name != ""
    and plan_path(safe_name).exists()
    and safe_name != st.session_state["active_plan"]
)

if plan_will_overwrite:
    st.warning(f"Saving will overwrite the existing plan `{safe_name}`.")
    confirm_overwrite = st.checkbox(f"Yes, overwrite `{safe_name}`")
else:
    confirm_overwrite = True

if st.button("Save plan"):
    if safe_name == "":
        st.error("Please enter a plan name.")
    elif plan_will_overwrite and not confirm_overwrite:
        st.error("Please confirm that you want to overwrite the existing plan.")
    else:
        save_plan(edited, safe_name)
        st.session_state["active_plan"] = safe_name
        st.success(f"Plan saved as {safe_name}.json")
        st.rerun()

st.caption(f"Active plan: `{st.session_state['active_plan']}`")

st.subheader("Plan")

st.markdown(
    """
    <style>
    .semester-title {
        font-size: 1.1rem;
        font-weight: 700;
        margin-bottom: 0.75rem;
    }
    .course-row {
        display: flex;
        flex-wrap: wrap;
        gap: 0.75rem;
        align-items: stretch;
    }
    .course-card {
        border: 1px solid rgba(128, 128, 128, 0.3);
        border-radius: 10px;
        padding: 0.75rem;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
        min-width: 180px;
        max-width: 240px;
        flex: 1 1 180px;
    }
    .course-card.pflichtmodul {
        background-color: rgba(255, 215, 0, 0.28);
    }
    .course-card.wahlpflichtmodul {
        background-color: rgba(128, 0, 32, 0.28);
    }
    .course-name {
        font-weight: 650;
        margin-bottom: 0.25rem;
    }
    .course-cp {
        font-size: 0.9rem;
        opacity: 0.75;
    }
    .semester-total {
        margin-top: 0.75rem;
        font-weight: 700;
    }
    </style>
    """,
    unsafe_allow_html=True
)

semesters = ["Semester 1", "Semester 2", "Semester 3", "Semester 4", "Semester 5", "Semester 6"]

for semester in semesters:
    sem_df = edited[edited["semester"] == semester]
    total_cp = int(sem_df["cp"].sum())

    course_cards = ""
    for _, row in sem_df.iterrows():
        selected_type = str(row["selected_type"]).strip()
        card_class = "pflichtmodul" if selected_type == "Pflichtmodul" else "wahlpflichtmodul"
        course_cards += f"""
        <div class="course-card {card_class}">
            <div class="course-name">{row['code']}: {row['course']}</div>
            <div class="course-cp">{int(row['cp'])} CP</div>
        </div>
        """

    if course_cards == "":
        course_cards = "<p style='opacity: 0.55;'>No courses assigned yet.</p>"

    st.markdown(
        f"""
        <div class="semester-title">{semester}</div>
        <div class="course-row">
            {course_cards}
        </div>
        <div class="semester-total">Total: {total_cp} CP</div>
        """,
        unsafe_allow_html=True
    )

    st.divider()