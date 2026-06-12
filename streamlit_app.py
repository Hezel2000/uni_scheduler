import json
from pathlib import Path
import random
import re
import textwrap

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Course Scheduler", layout="wide")

st.title("Course Scheduler")

MODULE_FOLDER = Path("Module als json")
ORIGINAL_MODULE_FOLDER = Path("Module als json original")
PLANS_FOLDER = Path("plans")
PLANS_FOLDER.mkdir(exist_ok=True)

SEMESTERS_ALL = ["Unplanned", "1", "2", "3", "4", "5", "6"]
BSC_SEMESTERS = ["1", "2", "3", "4", "5", "6"]
MSC_SEMESTERS = ["1", "2", "3", "4"]
MODULE_TYPES = ["Pflichtmodul", "Wahlpflichtmodul", "Importmodul"]


# -----------------------------------------------------------------------------
# Generic helpers
# -----------------------------------------------------------------------------

def clean_file_name(name):
    """Create a safe file name from a user-provided name."""
    name = str(name).strip()
    name = re.sub(r"[^a-zA-Z0-9_\- ]", "", name)
    name = name.replace(" ", "_")
    return name


def clean_plan_name(name):
    """Create a safe file name from a user-provided plan name."""
    return clean_file_name(name)


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


def default_selected_type_from_module_type(module_type):
    """Infer the selected planning type from the original Modul-Typ string."""
    module_type = str(module_type)

    if "Importmodul" in module_type:
        return "Importmodul"
    if "Wahlpflichtmodul" in module_type:
        return "Wahlpflichtmodul"
    if "Pflichtmodul" in module_type:
        return "Pflichtmodul"

    return "Pflichtmodul"


def normalize_semester_value(value):
    """Convert 'Semester 1' to '1', keep 'Unplanned' unchanged."""
    value = str(value)
    if value.startswith("Semester "):
        return value.replace("Semester ", "")
    return value


# -----------------------------------------------------------------------------
# Plan helpers
# -----------------------------------------------------------------------------

def plan_path(plan_name):
    """Return the JSON path for a named plan."""
    safe_name = clean_plan_name(plan_name)
    return PLANS_FOLDER / f"{safe_name}.json"


def list_saved_plans():
    """List all saved plans without the .json suffix."""
    return sorted(path.stem for path in PLANS_FOLDER.glob("*.json"))


def load_plan(plan_name):
    """Load saved semester assignments for a named plan if it exists."""
    path = plan_path(plan_name)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_plan(df, plan_name):
    """Save semester assignment and selected module type, not full module descriptions."""
    path = plan_path(plan_name)
    plan = {}

    for _, row in df.iterrows():
        plan[row["code"]] = {
            "semester": row["semester"],
            "selected_type": row["selected_type"],
        }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=4, ensure_ascii=False)


def delete_plan(plan_name):
    """Delete a named plan if it exists."""
    path = plan_path(plan_name)
    if path.exists():
        path.unlink()


# -----------------------------------------------------------------------------
# Module restore helpers
# -----------------------------------------------------------------------------

def original_module_path(module_path):
    """Return the matching original module path for a working module path."""
    return ORIGINAL_MODULE_FOLDER / module_path.name



def restore_module_from_original(module_path):
    """Restore a working module JSON from the matching file in the original folder."""
    source_path = original_module_path(module_path)

    if not source_path.exists():
        return False

    with open(source_path, "r", encoding="utf-8") as source_file:
        original_module = json.load(source_file)

    with open(module_path, "w", encoding="utf-8") as target_file:
        json.dump(original_module, target_file, indent=4, ensure_ascii=False)

    return True


# Helper to clear Streamlit widget state for the edit form of one module
def clear_module_form_state(module_path):
    """Clear Streamlit widget state for the edit form of one module."""
    key_prefix = f"edit_{module_path.stem}"
    keys_to_delete = [
        key for key in st.session_state.keys()
        if str(key).startswith(key_prefix)
    ]

    for key in keys_to_delete:
        del st.session_state[key]


# -----------------------------------------------------------------------------
# Dialogs
# -----------------------------------------------------------------------------

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


@st.dialog("Delete module?")
def delete_module_dialog(module_path):
    """Ask for confirmation before deleting an existing module JSON file."""
    st.warning(f"The module file `{module_path.name}` will be deleted.")
    st.write("This cannot be undone unless you have a backup or Git history.")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Delete module", type="primary"):
            module_path.unlink()
            st.success(f"Deleted `{module_path}`.")
            st.rerun()

    with col2:
        if st.button("Cancel"):
            st.rerun()


@st.dialog("Restore original module?")
def restore_module_dialog(module_path):
    """Ask for confirmation before restoring a module from the original folder."""
    source_path = original_module_path(module_path)

    st.warning(f"The module `{module_path.name}` will be restored from `{source_path}`.")
    st.write("All current edits to this module will be overwritten.")

    if not source_path.exists():
        st.error(f"No matching original file found: `{source_path}`")
        if st.button("Close"):
            st.rerun()
        return

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Restore original", type="primary"):
            restored = restore_module_from_original(module_path)
            if restored:
                clear_module_form_state(module_path)
                refresh_key = f"refresh_{module_path.stem}"
                st.session_state[refresh_key] = st.session_state.get(refresh_key, 0) + 1
                st.toast(f"Restored {module_path.name} from original.")
            else:
                st.error(f"Could not restore `{module_path.name}`.")
            st.rerun()

    with col2:
        if st.button("Cancel"):
            st.rerun()


# -----------------------------------------------------------------------------
# Module loading
# -----------------------------------------------------------------------------

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
        default_selected_type = default_selected_type_from_module_type(module_type)

        plan_entry = plan.get(code, {})
        if isinstance(plan_entry, str):
            saved_semester = normalize_semester_value(plan_entry)
            saved_selected_type = default_selected_type
        else:
            saved_semester = normalize_semester_value(plan_entry.get("semester", "Unplanned"))
            saved_selected_type = plan_entry.get("selected_type", default_selected_type)

        rows.append({
            "code": code,
            "course": name_de or name_en or code,
            "cp": extract_cp(cp_text),
            "sws": extract_sws(sws_text),
            "semester": saved_semester,
            "selected_type": saved_selected_type,
            "type": module_type,
            "responsible": module.get("Modulbeauftragte / Modulbeauftragter", ""),
        })

    return pd.DataFrame(rows)


# -----------------------------------------------------------------------------
# PDF helpers
# -----------------------------------------------------------------------------

def pdf_safe_text(text):
    """Make text safe for a simple PDF text stream while preserving German umlauts."""
    text = str(text).replace("\r", " ").replace("\t", " ")
    text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return text


def wrapped_lines(label, value, width=95, max_chars=1200):
    """Create wrapped text lines for one module field."""
    value = str(value).strip()
    if value == "":
        value = "keine"

    if len(value) > max_chars:
        value = value[:max_chars].rstrip() + " ..."

    lines = [label]
    for paragraph in value.split("\n"):
        paragraph = paragraph.strip()
        if paragraph == "":
            lines.append("")
        else:
            lines.extend(textwrap.wrap(paragraph, width=width))
    return lines


def module_lines_for_pdf(module):
    """Convert one module JSON dictionary into readable PDF text lines."""
    code = module.get("Modul-Code", "")
    name_de = module.get("Modul-Name-de", "")
    name_en = module.get("Modul-Name-en", "")
    module_type = module.get("Modul-Typ", "")
    cp = module.get("Anzhal CP und Arbeitsaufwand", "")
    sws = module.get("Anzahl SWS", "")
    responsible = module.get("Modulbeauftragte / Modulbeauftragter", "")

    lines = [
        f"## {code}: {name_de}",
        f"English title: {name_en}",
        f"Type: {module_type}",
        f"CP / workload: {cp}",
        f"SWS: {sws}",
        f"Responsible: {responsible}",
        "",
    ]

    lines.extend(wrapped_lines("Inhalte:", module.get("Inhalte", "")))
    lines.append("")
    lines.extend(wrapped_lines("Lernergebnisse / Kompetenzziele:", module.get("Lernergebnisse / Kompetenzziele", "")))
    lines.append("")
    lines.extend(wrapped_lines("Modulprüfung:", module.get("Modulprüfung", {}), max_chars=600))
    lines.append("")
    lines.append("-" * 90)
    lines.append("")
    return lines


def simple_pdf_from_lines(lines, title="Modulhandbuch"):
    """Create a simple multi-page PDF from plain text lines without external dependencies."""
    max_lines_per_page = 46
    pages = []
    current_page = []

    for line in lines:
        if len(current_page) >= max_lines_per_page:
            pages.append(current_page)
            current_page = []
        current_page.append(line)

    if current_page:
        pages.append(current_page)

    objects = []

    def add_object(content):
        objects.append(content)
        return len(objects)

    catalog_id = add_object("<< /Type /Catalog /Pages 2 0 R >>")
    pages_id = add_object("")
    font_regular_id = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    font_bold_id = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")

    page_ids = []

    for page_number, page_lines in enumerate(pages, start=1):
        stream_lines = []

        y = 800
        for line in page_lines:
            if line.startswith("# "):
                font = "/F2 22 Tf"
                clean_line = line.replace("# ", "", 1)
                line_spacing = 28
            elif line.startswith("## "):
                font = "/F2 14 Tf"
                clean_line = line.replace("## ", "", 1)
                line_spacing = 20
            elif line.endswith(":"):
                font = "/F2 10 Tf"
                clean_line = line
                line_spacing = 14
            else:
                font = "/F1 10 Tf"
                clean_line = line
                line_spacing = 14

            stream_lines.append(f"BT {font} 50 {y} Td ({pdf_safe_text(clean_line)}) Tj ET")
            y -= line_spacing

        # Page number at bottom right
        stream_lines.append(f"BT /F1 9 Tf 520 30 Td ({page_number}) Tj ET")

        stream = "\n".join(stream_lines)
        stream_bytes = stream.encode("cp1252", errors="replace")
        content_id = add_object(
            f"<< /Length {len(stream_bytes)} >>\nstream\n" +
            stream_bytes.decode("cp1252", errors="replace") +
            "\nendstream"
        )
        page_id = add_object(
            f"<< /Type /Page /Parent {pages_id} 0 R "
            f"/MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 {font_regular_id} 0 R /F2 {font_bold_id} 0 R >> >> "
            f"/Contents {content_id} 0 R >>"
        )
        page_ids.append(page_id)

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[pages_id - 1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>"

    pdf = bytearray()
    pdf.extend(b"%PDF-1.4\n")
    offsets = [0]

    for object_number, content in enumerate(objects, start=1):
        offsets.append(len(pdf))
        encoded_content = content.encode("cp1252", errors="replace")
        pdf.extend(f"{object_number} 0 obj\n".encode("cp1252"))
        pdf.extend(encoded_content)
        pdf.extend(b"\nendobj\n")

    xref_position = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("cp1252"))
    pdf.extend(b"0000000000 65535 f \n")

    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("cp1252"))

    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
        f"startxref\n{xref_position}\n%%EOF".encode("cp1252")
    )

    return bytes(pdf)


def create_random_modules_pdf(number_of_modules=5):
    """Create a PDF with a readable summary of random modules."""
    module_paths = sorted(MODULE_FOLDER.glob("*.json"))
    if not module_paths:
        return None, []

    selected_paths = random.sample(module_paths, min(number_of_modules, len(module_paths)))
    selected_modules = []

    for module_path in selected_paths:
        with open(module_path, "r", encoding="utf-8") as f:
            selected_modules.append(json.load(f))

    lines = [
        "# Modulhandbuch",
        f"Random module sample with {len(selected_modules)} modules",
        "",
        "=" * 90,
        "",
    ]

    for module in selected_modules:
        lines.extend(module_lines_for_pdf(module))

    pdf_bytes = simple_pdf_from_lines(lines, title="Modulhandbuch")
    return pdf_bytes, selected_modules


# -----------------------------------------------------------------------------
# Optional reference BSc plan
# -----------------------------------------------------------------------------

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
    """Create a reference BSc plan if it does not yet exist."""
    reference_plan_name = "BSc_reference_plan"
    path = plan_path(reference_plan_name)

    if path.exists() or not MODULE_FOLDER.exists():
        return

    semester_rules = [
        ("1", [
            {"code": "BP1"},
            {"code": "BP2"},
            {"code": "BP15a"},
            {"code": "BP16a"},
            {"code": "BP17"},
        ]),
        ("2", [
            {"name_terms": ["wissenschaft", "arbeiten"]},
            {"name_terms": ["karten", "profile"]},
            {"name_terms": ["gelände"]},
            {"code": "BP15b"},
            {"code": "BP16b"},
            {"code": "BP18"},
        ]),
        ("3", [
            {"code": "BP6"},
            {"name_terms": ["erd", "lebensgeschichte"]},
            {"name_terms": ["paläontologie"]},
            {"code": "BP8"},
            {"code": "BP4"},
            {"code": "BP13"},
        ]),
        ("4", [
            {"code": "BP10"},
            {"code": "BP11"},
            {"code": "BP12"},
            {"name_terms": ["planetare", "geologie"]},
            {"name_terms": ["petrologie"]},
            {"name_terms": ["seminar"]},
        ]),
        ("5", [
            {"name_terms": ["berufspraktikum"]},
            {"name_terms": ["optionalmodul"]},
        ]),
        ("6", [
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

                if module_matches(module, code=rule.get("code"), name_terms=rule.get("name_terms")):
                    module_type = str(module.get("Modul-Typ", ""))
                    plan[code] = {
                        "semester": semester,
                        "selected_type": default_selected_type_from_module_type(module_type),
                    }
                    used_codes.add(code)
                    break

    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=4, ensure_ascii=False)


ensure_reference_bsc_plan()


# -----------------------------------------------------------------------------
# Sidebar plan management
# -----------------------------------------------------------------------------

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
    index=plan_options.index(st.session_state["active_plan"]),
)

if selected_plan != st.session_state["active_plan"]:
    st.session_state["active_plan"] = selected_plan
    st.rerun()

new_plan_name = st.sidebar.text_input("Save as", value=st.session_state["active_plan"])

if saved_plans:
    st.sidebar.divider()
    st.sidebar.subheader("Delete plan")
    plan_to_delete = st.sidebar.selectbox("Plan to delete", options=saved_plans)

    if st.sidebar.button("Delete selected plan"):
        delete_plan_dialog(plan_to_delete)


# -----------------------------------------------------------------------------
# Tabs
# -----------------------------------------------------------------------------

bsc_plan_tab, msc_plan_tab, module_management_tab, pdf_tab = st.tabs([
    "BSc Plan",
    "MSc Plan",
    "Module management",
    "PDF export",
])


# -----------------------------------------------------------------------------
# Plan tab renderer
# -----------------------------------------------------------------------------

st.markdown(
    """
    <style>
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
    unsafe_allow_html=True,
)


def render_plan_tab(
    degree_label,
    code_prefix,
    semesters,
    semester_options,
    working_key,
    working_plan_key,
    unplanned_editor_key,
    planned_editor_key,
    save_button_key,
):
    """Render one independent plan tab for one degree programme."""
    courses = load_modules()
    courses = courses[courses["code"].astype(str).str.startswith(code_prefix)].copy()
    courses = courses[["code", "course", "cp", "sws", "semester", "selected_type", "type", "responsible"]]

    if (
        working_key not in st.session_state
        or st.session_state.get(working_plan_key) != st.session_state["active_plan"]
    ):
        st.session_state[working_key] = courses.copy()
        st.session_state[working_plan_key] = st.session_state["active_plan"]
    else:
        saved_choices = st.session_state[working_key][["code", "semester", "selected_type"]].copy()
        st.session_state[working_key] = courses.drop(columns=["semester", "selected_type"]).merge(
            saved_choices,
            on="code",
            how="left",
        )
        st.session_state[working_key]["semester"] = st.session_state[working_key]["semester"].fillna("Unplanned")
        st.session_state[working_key]["selected_type"] = st.session_state[working_key]["selected_type"].fillna(
            st.session_state[working_key]["type"].apply(default_selected_type_from_module_type)
        )
        st.session_state[working_key] = st.session_state[working_key][
            ["code", "course", "cp", "sws", "semester", "selected_type", "type", "responsible"]
        ]

    working_courses = st.session_state[working_key].copy()

    st.info("The cells in the columns with the three lines and a pen symbol — Semester and Selected type — can be edited by clicking twice on them. Clicking the first time on a cell in these columns selects it, clicking the second time displayse the dropdown, from which a selection can be made. This way modules can be added, removed, ... to/from the plan.")
    left_col, right_col = st.columns(2)

    column_config = {
        "code": st.column_config.TextColumn("Code"),
        "course": st.column_config.TextColumn("Course"),
        "cp": st.column_config.NumberColumn("CP", format="%d"),
        "sws": st.column_config.NumberColumn("SWS", format="%d"),
        "semester": st.column_config.SelectboxColumn("Semester", options=semester_options),
        "selected_type": st.column_config.SelectboxColumn("Selected type", options=MODULE_TYPES),
        "type": st.column_config.TextColumn("Type"),
        "responsible": st.column_config.TextColumn("Responsible"),
    }

    with left_col:
        st.markdown("### Not yet in plan")
        unplanned_courses = working_courses[working_courses["semester"] == "Unplanned"]
        edited_unplanned_courses = st.data_editor(
            unplanned_courses,
            column_config=column_config,
            disabled=["code", "course", "cp", "sws", "type", "responsible"],
            hide_index=True,
            use_container_width=True,
            key=unplanned_editor_key,
        )

    with right_col:
        st.markdown("### Already in plan")
        planned_courses = working_courses[working_courses["semester"] != "Unplanned"]
        edited_planned_courses = st.data_editor(
            planned_courses,
            column_config=column_config,
            disabled=["code", "course", "cp", "sws", "type", "responsible"],
            hide_index=True,
            use_container_width=True,
            key=planned_editor_key,
        )

    edited = pd.concat([edited_planned_courses, edited_unplanned_courses], ignore_index=True)
    edited = edited[["code", "course", "cp", "sws", "semester", "selected_type", "type", "responsible"]]

    old_state = st.session_state[working_key].sort_values("code").reset_index(drop=True)
    new_state = edited.sort_values("code").reset_index(drop=True)

    if not old_state.equals(new_state):
        st.session_state[working_key] = edited.copy()
        st.rerun()

    safe_name = clean_plan_name(new_plan_name)
    plan_will_overwrite = safe_name != "" and plan_path(safe_name).exists()

    if st.button("Save plan", key=save_button_key):
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

    assigned_modules = edited[edited["semester"].isin(semesters)]
    plan_total_cp_header = int(assigned_modules["cp"].sum())
    plan_total_sws_header = int(assigned_modules["sws"].sum())

    st.subheader(f"{degree_label} Plan ({plan_total_cp_header} CP · {plan_total_sws_header} SWS)")

    for semester in semesters:
        sem_df = edited[edited["semester"] == semester].copy()
        sem_df["sort_order"] = sem_df["selected_type"].apply(
            lambda x: 1 if str(x).strip() == "Importmodul" else 0
        )
        sem_df = sem_df.sort_values(["sort_order", "code"])

        total_cp = int(sem_df["cp"].sum())
        total_sws = int(sem_df["sws"].sum())

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


with bsc_plan_tab:
    render_plan_tab(
        degree_label="BSc",
        code_prefix="B",
        semesters=BSC_SEMESTERS,
        semester_options=SEMESTERS_ALL,
        working_key="bsc_working_plan_df",
        working_plan_key="bsc_working_plan_name",
        unplanned_editor_key="bsc_unplanned_courses_editor",
        planned_editor_key="bsc_planned_courses_editor",
        save_button_key="save_bsc_plan",
    )


with msc_plan_tab:
    render_plan_tab(
        degree_label="MSc",
        code_prefix="M",
        semesters=MSC_SEMESTERS,
        semester_options=["Unplanned", "1", "2", "3", "4"],
        working_key="msc_working_plan_df",
        working_plan_key="msc_working_plan_name",
        unplanned_editor_key="msc_unplanned_courses_editor",
        planned_editor_key="msc_planned_courses_editor",
        save_button_key="save_msc_plan",
    )


# -----------------------------------------------------------------------------
# PDF export tab
# -----------------------------------------------------------------------------

with pdf_tab:
    st.subheader("PDF export")
    st.info("This is a simple demonstrator to illustrate what is possible.")
    st.write("Generate a PDF preview containing a sensible summary of five random modules.")

    if st.button("Generate PDF with 5 random modules"):
        pdf_bytes, selected_modules = create_random_modules_pdf(number_of_modules=5)
        st.session_state["random_modules_pdf_bytes"] = pdf_bytes
        st.session_state["random_modules_pdf_selection"] = selected_modules

    if "random_modules_pdf_bytes" in st.session_state and st.session_state["random_modules_pdf_bytes"] is not None:
        selected_modules = st.session_state.get("random_modules_pdf_selection", [])
        selected_labels = [
            f"{module.get('Modul-Code', '')}: {module.get('Modul-Name-de', module.get('Modul-Name-en', ''))}"
            for module in selected_modules
        ]

        st.markdown("### Selected modules")
        for label in selected_labels:
            st.write(f"- {label}")

        st.download_button(
            label="Download PDF",
            data=st.session_state["random_modules_pdf_bytes"],
            file_name="random_modules.pdf",
            mime="application/pdf",
        )
    else:
        st.info("Click the button above to generate a PDF.")

# -----------------------------------------------------------------------------
# Module management tab
# -----------------------------------------------------------------------------

with module_management_tab:
    st.subheader("Module management")

    module_action = st.radio(
        "What do you want to do?",
        options=["Add module", "Edit module", "Delete module"],
        horizontal=True,
    )

    def get_module_options():
        """Return a mapping from readable module labels to module file paths."""
        module_files = sorted(MODULE_FOLDER.glob("*.json"))
        module_options = {}

        for module_file in module_files:
            with open(module_file, "r", encoding="utf-8") as f:
                module_data = json.load(f)

            module_code = module_data.get("Modul-Code", module_file.stem)
            module_name = module_data.get("Modul-Name-de", module_data.get("Modul-Name-en", ""))
            module_options[f"{module_code}: {module_name}"] = module_file

        return module_options

    def first_version(module_data):
        """Return the first version string from a module JSON."""
        version_value = module_data.get("Version", ["2025-01-06"])
        if isinstance(version_value, list) and len(version_value) > 0:
            return str(version_value[0])
        if isinstance(version_value, str):
            return version_value
        return "2025-01-06"

    def semester_table_dataframe(module_data, modul_name_de, anzahl_sws, cp):
        """Return the semester table as a DataFrame with standard columns."""
        columns = ["Titel", "LV-Form", "SWS", "CP", "1", "2", "3", "4", "5", "6"]
        semester_table = module_data.get("Semester-Tabelle", [])

        if semester_table:
            return pd.DataFrame(semester_table, columns=columns[:len(semester_table[0])])

        return pd.DataFrame(
            [{
                "Titel": modul_name_de,
                "LV-Form": "",
                "SWS": anzahl_sws,
                "CP": cp,
                "1": "X",
                "2": "",
                "3": "",
                "4": "",
                "5": "",
                "6": "",
            }]
        )

    def module_form(mode, module_data=None, selected_module_path=None):
        """Render the shared add/edit module form and save a module JSON."""
        module_data = module_data or {}
        if mode == "add":
            key_prefix = "add"
        else:
            refresh_token = st.session_state.get(f"refresh_{selected_module_path.stem}", 0)
            key_prefix = f"edit_{selected_module_path.stem}_{refresh_token}"

        modul_code_default = module_data.get("Modul-Code", "")
        modul_name_de_default = module_data.get("Modul-Name-de", "")
        modul_name_en_default = module_data.get("Modul-Name-en", "")
        modul_typ_default = module_data.get("Modul-Typ", "Pflichtmodul")
        cp_default = int(extract_cp(module_data.get("Anzhal CP und Arbeitsaufwand", "6 CP = 180 h"))) or 6
        sws_default = int(extract_sws(module_data.get("Anzahl SWS", "4 SWS"))) or 4
        version_default = first_version(module_data)

        pruefung = module_data.get("Modulprüfung", {})
        nachweise = module_data.get("Studiennachweise/ ggf. als Prüfungsvorleistungen", {})
        aenderung_dict = module_data.get("Änderung", {})
        aenderung_default = (
            aenderung_dict.get(version_default, "Bereitstellung")
            if isinstance(aenderung_dict, dict)
            else "Bereitstellung"
        )

        with st.form(f"{key_prefix}_module_form"):
            st.markdown("### Basic information")
            col1, col2, col3 = st.columns(3)

            with col1:
                modul_code = st.text_input(
                    "Modul-Code",
                    value=modul_code_default,
                    placeholder="e.g. BP99",
                    key=f"{key_prefix}_code",
                )
                modul_typ = st.selectbox(
                    "Modul-Typ",
                    options=MODULE_TYPES,
                    index=MODULE_TYPES.index(modul_typ_default) if modul_typ_default in MODULE_TYPES else 0,
                    key=f"{key_prefix}_type",
                )
                cp = st.number_input("CP", min_value=0, step=1, value=cp_default, key=f"{key_prefix}_cp")

            with col2:
                modul_name_de = st.text_input(
                    "Modul-Name-de",
                    value=modul_name_de_default,
                    key=f"{key_prefix}_name_de",
                )
                anzahl_sws = st.number_input(
                    "Anzahl SWS",
                    min_value=0,
                    step=1,
                    value=sws_default,
                    key=f"{key_prefix}_sws",
                )
                haeufigkeit = st.text_input(
                    "Häufigkeit des Angebots",
                    value=module_data.get("Häufigkeit des Angebots", "jährlich"),
                    key=f"{key_prefix}_haeufigkeit",
                )

            with col3:
                modul_name_en = st.text_input(
                    "Modul-Name-en",
                    value=modul_name_en_default,
                    key=f"{key_prefix}_name_en",
                )
                dauer = st.text_input(
                    "Dauer des Moduls",
                    value=module_data.get("Dauer des Moduls", "1 Semester"),
                    key=f"{key_prefix}_dauer",
                )
                version = st.text_input("Version", value=version_default, key=f"{key_prefix}_version")

            st.markdown("### Workload")
            col1, col2, col3 = st.columns(3)
            with col1:
                arbeitsaufwand = st.number_input(
                    "Arbeitsaufwand in Stunden",
                    min_value=0,
                    step=30,
                    value=int(cp * 30),
                    key=f"{key_prefix}_workload",
                )
            with col2:
                kontaktstudium = st.text_input(
                    "Kontaktstudium",
                    value=module_data.get("Kontaktstudium", f"{anzahl_sws} SWS"),
                    key=f"{key_prefix}_kontakt",
                )
            with col3:
                selbststudium = st.text_input(
                    "Selbststudium",
                    value=module_data.get("Selbststudium", ""),
                    key=f"{key_prefix}_selbst",
                )

            st.markdown("### Content and learning outcomes")
            inhalte = st.text_area(
                "Inhalte",
                value=module_data.get("Inhalte", ""),
                height=160,
                key=f"{key_prefix}_inhalte",
            )
            lernergebnisse = st.text_area(
                "Lernergebnisse / Kompetenzziele",
                value=module_data.get("Lernergebnisse / Kompetenzziele", ""),
                height=160,
                key=f"{key_prefix}_lernergebnisse",
            )

            st.markdown("### Requirements and organisational information")
            teilnahmevoraussetzungen = st.text_area(
                "Teilnahmevoraussetzungen für Modul bzw. für einzelne Lehrveranstaltungen des Moduls",
                value=module_data.get(
                    "Teilnahmevoraussetzungen für Modul bzw. für einzelne Lehrveranstaltungen des Moduls",
                    "keine",
                ),
                height=80,
                key=f"{key_prefix}_teilnahme",
            )
            empfohlene_voraussetzungen = st.text_area(
                "Empfohlene Voraussetzungen",
                value=module_data.get("Empfohlene Voraussetzungen", "keine"),
                height=80,
                key=f"{key_prefix}_empfohlen",
            )
            organisatorische_hinweise = st.text_area(
                "Organisatorische Hinweise",
                value=module_data.get("Organisatorische Hinweise", "keine"),
                height=80,
                key=f"{key_prefix}_orga",
            )

            st.markdown("### Study programme information")
            zuordnung = st.text_input(
                "Zuordnung des Moduls (Studiengang / Fachbereich)",
                value=module_data.get("Zuordnung des Moduls (Studiengang / Fachbereich)", "B.Sc. Geowissenschaften / FB 11"),
                key=f"{key_prefix}_zuordnung",
            )
            verwendbarkeit = st.text_input(
                "Verwendbarkeit des Moduls für andere Studiengänge",
                value=module_data.get("Verwendbarkeit des Moduls für andere Studiengänge", ""),
                key=f"{key_prefix}_verwendbarkeit",
            )
            modulbeauftragte = st.text_input(
                "Modulbeauftragte / Modulbeauftragter",
                value=module_data.get("Modulbeauftragte / Modulbeauftragter", ""),
                key=f"{key_prefix}_beauftragte",
            )

            st.markdown("### Assessment and teaching")
            col1, col2 = st.columns(2)
            with col1:
                teilnahmenachweise = st.text_input(
                    "Teilnahmenachweise",
                    value=nachweise.get("Teilnahmenachweise", "keine"),
                    key=f"{key_prefix}_teilnahmenachweise",
                )
                leistungsnachweise = st.text_input(
                    "Leistungsnachweise",
                    value=nachweise.get("Leistungsnachweise", "keine"),
                    key=f"{key_prefix}_leistungsnachweise",
                )
                lehr_lernformen = st.text_input(
                    "Lehr- / Lernformen",
                    value=module_data.get("Lehr- / Lernformen", ""),
                    key=f"{key_prefix}_lehrform",
                )
            with col2:
                sprache = st.text_input(
                    "Unterrichts- / Prüfungssprache",
                    value=module_data.get("Unterrichts- / Prüfungssprache", "Deutsch"),
                    key=f"{key_prefix}_sprache",
                )
                modulabschlusspruefung = st.text_input(
                    "Modulabschlussprüfung bestehend aus",
                    value=pruefung.get("Modulabschlussprüfung bestehend aus", ""),
                    key=f"{key_prefix}_abschluss",
                )
                kumulative_pruefung = st.text_input(
                    "kumulative Modulprüfung bestehend aus",
                    value=pruefung.get("kumulative Modulprüfung bestehend aus", ""),
                    key=f"{key_prefix}_kumulativ",
                )
                bildung_modulnote = st.text_input(
                    "Bildung der Modulnote bei kumulativen Modulprüfungen",
                    value=pruefung.get("Bildung der Modulnote bei kumulativen Modulprüfungen", ""),
                    key=f"{key_prefix}_note",
                )

            st.markdown("### Semester table")
            st.write("Add one row for each course unit belonging to this module.")
            semester_table_df = semester_table_dataframe(module_data, modul_name_de, anzahl_sws, cp)
            edited_semester_table = st.data_editor(
                semester_table_df,
                num_rows="dynamic",
                hide_index=True,
                use_container_width=True,
                key=f"{key_prefix}_semester_table",
            )

            bemerkungen = st.text_area(
                "Bemerkungen",
                value=module_data.get("Bemerkungen", "keine"),
                height=80,
                key=f"{key_prefix}_bemerkungen",
            )
            aenderung = st.text_input("Änderung", value=aenderung_default, key=f"{key_prefix}_aenderung")

            button_label = "Save new module" if mode == "add" else "Save edited module"
            submitted = st.form_submit_button(button_label)

        if submitted:
            if modul_code.strip() == "":
                st.error("Please enter a Modul-Code.")
                return
            if modul_name_de.strip() == "" and modul_name_en.strip() == "":
                st.error("Please enter at least a German or English module name.")
                return

            safe_module_code = clean_file_name(modul_code)
            output_path = MODULE_FOLDER / f"{safe_module_code}.json"

            if mode == "add" and output_path.exists():
                st.error(f"A module file named `{output_path.name}` already exists. Please choose another Modul-Code.")
                return

            if mode == "edit" and selected_module_path is not None and output_path != selected_module_path and output_path.exists():
                st.error(f"A module file named `{output_path.name}` already exists. Please choose another Modul-Code.")
                return

            semester_table = edited_semester_table.fillna("").values.tolist()

            new_module = {
                "Modul-Code": modul_code.strip(),
                "Modul-Name-en": modul_name_en.strip(),
                "Modul-Name-de": modul_name_de.strip(),
                "Modul-Typ": modul_typ,
                "Anzhal CP und Arbeitsaufwand": f"{int(cp)} CP = {int(arbeitsaufwand)} h",
                "Anzahl SWS": f"{int(anzahl_sws)} SWS",
                "Kontaktstudium": kontaktstudium,
                "Selbststudium": selbststudium,
                "Inhalte": inhalte,
                "Lernergebnisse / Kompetenzziele": lernergebnisse,
                "Teilnahmevoraussetzungen für Modul bzw. für einzelne Lehrveranstaltungen des Moduls": teilnahmevoraussetzungen,
                "Empfohlene Voraussetzungen": empfohlene_voraussetzungen,
                "Organisatorische Hinweise": organisatorische_hinweise,
                "Zuordnung des Moduls (Studiengang / Fachbereich)": zuordnung,
                "Verwendbarkeit des Moduls für andere Studiengänge": verwendbarkeit,
                "Häufigkeit des Angebots": haeufigkeit,
                "Dauer des Moduls": dauer,
                "Modulbeauftragte / Modulbeauftragter": modulbeauftragte,
                "Studiennachweise/ ggf. als Prüfungsvorleistungen": {
                    "Teilnahmenachweise": teilnahmenachweise,
                    "Leistungsnachweise": leistungsnachweise,
                },
                "Lehr- / Lernformen": lehr_lernformen,
                "Unterrichts- / Prüfungssprache": sprache,
                "Modulprüfung": {
                    "Modulabschlussprüfung bestehend aus": modulabschlusspruefung,
                    "kumulative Modulprüfung bestehend aus": kumulative_pruefung,
                    "Bildung der Modulnote bei kumulativen Modulprüfungen": bildung_modulnote,
                },
                "Semester-Tabelle": semester_table,
                "Bemerkungen": bemerkungen,
                "Version": [version],
                "Änderung": {
                    version: aenderung,
                },
            }

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(new_module, f, indent=4, ensure_ascii=False)

            if mode == "edit" and selected_module_path is not None and output_path != selected_module_path:
                selected_module_path.unlink()

            st.toast(f"Saved module as {output_path.name}.")
            st.rerun()

    module_options = get_module_options()

    if module_action == "Add module":
        st.markdown("## Add new module")
        module_form(mode="add")

    elif module_action == "Edit module":
        st.markdown("## Edit existing module")

        if module_options:
            selected_module_label = st.selectbox(
                "Select existing module to edit",
                options=list(module_options.keys()),
                key="module_to_edit",
            )
            selected_module_path = module_options[selected_module_label]

            with open(selected_module_path, "r", encoding="utf-8") as f:
                selected_module_data = json.load(f)

            restore_source_path = original_module_path(selected_module_path)
            if restore_source_path.exists():
                if st.button("Restore selected module from original"):
                    restore_module_dialog(selected_module_path)
            else:
                st.info(f"No original backup found for `{selected_module_path.name}` in `{ORIGINAL_MODULE_FOLDER}`.")

            module_form(mode="edit", module_data=selected_module_data, selected_module_path=selected_module_path)
        else:
            st.info("No module JSON files found yet.")

    elif module_action == "Delete module":
        st.markdown("## Delete module")

        if module_options:
            selected_module_label = st.selectbox(
                "Select module to delete",
                options=list(module_options.keys()),
                key="module_to_delete",
            )
            selected_module_path = module_options[selected_module_label]

            st.warning(f"Selected module file: `{selected_module_path}`")

            if st.button("Delete selected module", type="primary"):
                delete_module_dialog(selected_module_path)
        else:
            st.info("No module JSON files found yet.")
