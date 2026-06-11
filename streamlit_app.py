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

def extract_sws(sws_text):
    """Extract the first SWS number from strings such as '4 SWS'."""
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*SWS", str(sws_text))
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


# --- Helper functions for reference BSc plan
def module_matches(module, code=None, name_terms=None):
    """Return True if a module matches a code or all supplied name terms."""
    module_code = str(module.get("Modul-Code", "")).strip()
    name_de = str(module.get("Modul-Name-de", "")).lower()
    name_en = str(module.get("Modul-Name-en", "")).lower()
    combined_name = f"{name_de} {name_en}"

    if code is not None and module_code == code:
        return True

    if name_terms is not None:
        return all(term.lower() in combined_name for term in name_terms)

    return False


def ensure_reference_bsc_plan():
    """Create a reference BSc plan based on the uploaded semester overview if missing."""
    reference_plan_name = "BSc_reference_plan"
    path = plan_path(reference_plan_name)

    if path.exists() or not MODULE_FOLDER.exists():
        return

    semester_rules = [
        ("Semester 1", [
            {"code": "BP1"},
            {"code": "BP2"},
            {"code": "BP15a"},
            {"code": "BP16a"},
            {"code": "BP17"},
        ]),
        ("Semester 2", [
            {"name_terms": ["wissenschaft", "arbeiten"]},
            {"name_terms": ["karten", "profile"]},
            {"name_terms": ["gelände"]},
            {"code": "BP15b"},
            {"code": "BP16b"},
            {"code": "BP18"},
        ]),
        ("Semester 3", [
            {"code": "BP6"},
            {"name_terms": ["erd", "lebensgeschichte"]},
            {"name_terms": ["paläontologie"]},
            {"code": "BP8"},
            {"code": "BP4"},
            {"code": "BP13"},
        ]),
        ("Semester 4", [
            {"code": "BP10"},
            {"code": "BP11"},
            {"code": "BP12"},
            {"name_terms": ["planetare", "geologie"]},
            {"name_terms": ["petrologie"]},
            {"name_terms": ["seminar"]},
        ]),
        ("Semester 5", [
            {"name_terms": ["berufspraktikum"]},
            {"name_terms": ["optionalmodul"]},
        ]),
        ("Semester 6", [
            {"name_terms": ["bachelorarbeit"]},
            {"name_terms": ["optionalmodul"]},
        ]),
    ]

    modules = []
    for module_path in sorted(MODULE_FOLDER.glob("*.json")):
        with open(module_path, "r", encoding="utf-8") as f:
            modules.append(json.load(f))

    plan = {}
    used_codes = set()

    for semester, rules in semester_rules:
        for rule in rules:
            for module in modules:
                code = str(module.get("Modul-Code", "")).strip()

                if code in used_codes:
                    continue

                if module_matches(
                    module,
                    code=rule.get("code"),
                    name_terms=rule.get("name_terms"),
                ):
                    plan[code] = semester
                    used_codes.add(code)
                    break

    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=4, ensure_ascii=False)


# --- Modal dialog for overwriting plans
@st.dialog("Overwrite existing plan?")
def overwrite_plan_dialog(df, plan_name):
    """Ask for confirmation before overwriting an existing plan."""
    st.warning(f"The plan `{plan_name}` already exists. Saving will overwrite it.")
    st.write("This cannot be undone unless you have a backup or Git history.")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Overwrite", type="primary"):
            save_plan(df, plan_name)
            st.session_state["active_plan"] = plan_name
            st.success(f"Plan saved as {plan_name}.json")
            st.rerun()

    with col2:
        if st.button("Cancel"):
            st.rerun()


# --- Modal dialog for deleting plans
@st.dialog("Delete plan?")
def delete_plan_dialog(plan_name):
    """Ask for confirmation before deleting an existing plan."""
    st.warning(f"The plan `{plan_name}` will be deleted.")
    st.write("This cannot be undone unless you have a backup or Git history.")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Delete", type="primary"):
            delete_plan(plan_name)
            remaining_plans = list_saved_plans()
            st.session_state["active_plan"] = remaining_plans[0] if remaining_plans else "default"
            st.success(f"Deleted plan {plan_name}.")
            st.rerun()

    with col2:
        if st.button("Cancel"):
            st.rerun()


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
        sws_text = module.get("Anzahl SWS", "")

        module_type = str(module.get("Modul-Typ", ""))

        if "Importmodul" in module_type:
            default_selected_type = "Importmodul"
        elif "Wahlpflichtmodul" in module_type:
            default_selected_type = "Wahlpflichtmodul"
        elif "Pflichtmodul" in module_type:
            default_selected_type = "Pflichtmodul"
        else:
            default_selected_type = "Pflichtmodul"

        rows.append({
            "code": code,
            "course": name_de or name_en or code,
            "cp": extract_cp(cp_text),
            "sws": extract_sws(sws_text),
            "type": module_type,
            "selected_type": default_selected_type,
            "responsible": module.get("Modulbeauftragte / Modulbeauftragter", ""),
            "semester": plan.get(code, "Unplanned"),
        })

    return pd.DataFrame(rows)


ensure_reference_bsc_plan()

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

    if st.sidebar.button("Delete selected plan"):
        delete_plan_dialog(plan_to_delete)




bsc_plan_tab, add_module_tab = st.tabs(["BSc Plan", "Add Module"])

with bsc_plan_tab:
    courses = load_modules()
    # Only keep BSc modules
    courses = courses[courses["code"].astype(str).str.startswith("B")].copy()

    courses = courses.copy()
    for semester_name in ["Semester 1", "Semester 2", "Semester 3", "Semester 4", "Semester 5", "Semester 6"]:
        courses.loc[courses["semester"] == semester_name, "semester"] = semester_name.replace("Semester ", "")
    courses = courses[["code", "course", "cp", "sws", "semester", "selected_type", "type", "responsible"]]


    left_col, right_col = st.columns(2)

    with left_col:
        st.markdown("### Not yet in plan")
        unplanned_courses = courses[courses["semester"] == "Unplanned"]
        st.dataframe(
            unplanned_courses,
            hide_index=True,
            use_container_width=True,
        )

    with right_col:
        st.markdown("### Already in plan")
        planned_courses = courses[courses["semester"] != "Unplanned"]
        edited = st.data_editor(
            planned_courses,
            column_config={
                "code": st.column_config.TextColumn("Code"),
                "course": st.column_config.TextColumn("Course"),
                "cp": st.column_config.NumberColumn("CP", format="%d"),
                "sws": st.column_config.NumberColumn("SWS", format="%d"),
                "semester": st.column_config.SelectboxColumn(
                    "Semester",
                    options=["1", "2", "3", "4", "5", "6"]
                ),
                "selected_type": st.column_config.SelectboxColumn(
                    "Selected type",
                    options=["Pflichtmodul", "Wahlpflichtmodul", "Importmodul"]
                ),
                "type": st.column_config.TextColumn("Type"),
                "responsible": st.column_config.TextColumn("Responsible"),
            },
            disabled=["code", "course", "cp", "sws", "type", "responsible"],
            hide_index=True,
            use_container_width=True
        )

    edited = pd.concat([edited, unplanned_courses], ignore_index=True)


    # --- Save plan block with modal overwrite warning
    safe_name = clean_plan_name(new_plan_name)
    plan_will_overwrite = safe_name != "" and plan_path(safe_name).exists()

    if st.button("Save plan"):
        if safe_name == "":
            st.error("Please enter a plan name.")
        elif plan_will_overwrite:
            overwrite_plan_dialog(edited, safe_name)
        else:
            save_plan(edited, safe_name)
            st.session_state["active_plan"] = safe_name
            st.success(f"Plan saved as {safe_name}.json")
            st.rerun()

    st.caption(f"Active plan: `{st.session_state['active_plan']}`")

    # Calculate totals for the assigned plan, excluding unplanned modules
    semesters = ["1", "2", "3", "4", "5", "6"]
    assigned_modules = edited[edited["semester"].isin(semesters)]
    plan_total_cp_header = int(assigned_modules["cp"].sum())
    plan_total_sws_header = int(assigned_modules["sws"].sum())

    st.subheader(f"BSc Plan ({plan_total_cp_header} CP · {plan_total_sws_header} SWS)")

    st.markdown(
        """
        <style>
        .semester-title {
            font-size: 1.1rem;
            font-weight: 700;
            margin-bottom: 0.75rem;
        }
        .semester-plan-row {
            display: grid;
            grid-template-columns: 160px 1fr;
            gap: 0.75rem;
            align-items: start;
            margin-bottom: 1rem;
        }
        .semester-label {
            font-size: 1.1rem;
            font-weight: 700;
            padding: 0.75rem;
            border: 1px solid rgba(128, 128, 128, 0.3);
            border-radius: 10px;
            min-height: 220px;
            box-sizing: border-box;
            display: flex;
            flex-direction: column;
            justify-content: center;
            gap: 0.35rem;
        }
        .semester-label-main {
            font-size: 1.1rem;
            font-weight: 700;
        }
        .semester-label-stat {
            font-size: 0.95rem;
            font-weight: 600;
            opacity: 0.8;
        }
        .course-row {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(260px, 260px));
            gap: 0.75rem;
            align-items: stretch;
        }
        .course-card {
            border: 1px solid rgba(128, 128, 128, 0.3);
            border-radius: 10px;
            padding: 0.75rem;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
            width: 260px;
            height: 220px;
            overflow: hidden;
            box-sizing: border-box;
        }
        .course-card.pflichtmodul {
            background-color: rgba(255, 215, 0, 0.28);
        }
        .course-card.wahlpflichtmodul {
            background-color: rgba(128, 0, 32, 0.28);
        }
        .course-card.importmodul {
            background-color: rgba(0, 105, 148, 0.28);
        }
        .course-name {
            font-weight: 650;
            margin-bottom: 0.25rem;
        }
        .course-cp {
            font-size: 0.9rem;
            opacity: 0.75;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    plan_total_cp = 0
    plan_total_sws = 0

    for semester in semesters:
        sem_df = edited[edited["semester"] == semester]
        # Always display Importmodule at the far right
        sem_df = sem_df.copy()
        sem_df["sort_order"] = sem_df["selected_type"].apply(
            lambda x: 1 if str(x).strip() == "Importmodul" else 0
        )
        sem_df = sem_df.sort_values(["sort_order", "code"])
        total_cp = int(sem_df["cp"].sum())
        total_sws = int(sem_df["sws"].sum())
        plan_total_cp += total_cp
        plan_total_sws += total_sws

        course_cards = ""
        for _, row in sem_df.iterrows():
            selected_type = str(row["selected_type"]).strip()
            if selected_type == "Pflichtmodul":
                card_class = "pflichtmodul"
            elif selected_type == "Wahlpflichtmodul":
                card_class = "wahlpflichtmodul"
            elif selected_type == "Importmodul":
                card_class = "importmodul"
            else:
                card_class = "pflichtmodul"
            course_cards += (
                f'<div class="course-card {card_class}">'
                f'<div class="course-name">{row["code"]}: {row["course"]}</div>'
                f'<div class="course-cp">{int(row["cp"])} CP</div>'
                f'<div class="course-cp">{int(row["sws"])} SWS</div>'
                f'</div>'
            )

        if course_cards == "":
            course_cards = "<p style='opacity: 0.55;'>No courses assigned yet.</p>"

        semester_html = (
            f'<div class="semester-plan-row">'
            f'<div class="semester-label">'
            f'<div class="semester-label-main">{semester}</div>'
            f'<div class="semester-label-stat">{total_cp} CP</div>'
            f'<div class="semester-label-stat">{total_sws} SWS</div>'
            f'</div>'
            f'<div class="course-row">{course_cards}</div>'
            f'</div>'
        )

        st.markdown(semester_html, unsafe_allow_html=True)

        st.divider()


with add_module_tab:
    st.subheader("Add Module")
    st.info("This tab will later be used to add modules to the plan.")
