
import sqlite3
import io
import csv
from datetime import datetime

import pandas as pd
import streamlit as st


# -------------------- CONFIGURATION --------------------

st.set_page_config(
    page_title="Health Risk Assessment Platform",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

DB_NAME = "health_assessment.db"

GENDERS = ["Male", "Female", "Other", "Prefer not to say"]
SMOKING_OPTIONS = ["Never", "Former", "Current", "Prefer not to say"]
ACTIVITY_OPTIONS = ["Low", "Moderate", "High"]
CONDITIONS = [
    "Diabetes",
    "Hypertension",
    "Heart disease",
    "Asthma",
    "Thyroid disorder",
    "Other",
]


# -------------------- DATABASE --------------------

def connect_db():
    conn = sqlite3.connect(DB_NAME, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                age INTEGER NOT NULL,
                gender TEXT NOT NULL,
                height REAL NOT NULL,
                weight REAL NOT NULL,
                bmi REAL NOT NULL,
                smoking TEXT NOT NULL,
                activity TEXT NOT NULL,
                conditions TEXT DEFAULT '',
                contact TEXT DEFAULT '',
                address TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                deleted_at TEXT DEFAULT NULL
            )
        """)


def fetch_customers(include_deleted=False):
    with connect_db() as conn:
        if include_deleted:
            rows = conn.execute(
                "SELECT * FROM customers ORDER BY id DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM customers WHERE deleted_at IS NULL "
                "ORDER BY id DESC"
            ).fetchall()
    return pd.DataFrame([dict(row) for row in rows])


def get_customer(customer_id):
    with connect_db() as conn:
        row = conn.execute(
            "SELECT * FROM customers WHERE id = ?",
            (customer_id,),
        ).fetchone()
    return dict(row) if row else None


def calculate_bmi(height_cm, weight_kg):
    height_m = height_cm / 100
    return round(weight_kg / (height_m * height_m), 2)


def bmi_category(bmi):
    if bmi < 18.5:
        return "Below reference range"
    elif bmi < 25:
        return "Reference range"
    elif bmi < 30:
        return "Above reference range"
    return "High BMI range"


def validate_customer(data):
    errors = []

    if not data["name"].strip():
        errors.append("Customer name is required.")

    if not 1 <= data["age"] <= 120:
        errors.append("Age must be between 1 and 120.")

    if not 50 <= data["height"] <= 250:
        errors.append("Height must be between 50 and 250 cm.")

    if not 2 <= data["weight"] <= 500:
        errors.append("Weight must be between 2 and 500 kg.")

    contact = data["contact"].strip()
    if contact and not contact.replace("+", "").replace(" ", "").replace("-", "").isdigit():
        errors.append("Contact should contain digits, spaces, + or - only.")

    return errors


def find_duplicate(data, exclude_id=None):
    """Find likely duplicate active records."""
    query = """
        SELECT id, name, age, contact
        FROM customers
        WHERE deleted_at IS NULL
          AND LOWER(TRIM(name)) = LOWER(TRIM(?))
          AND age = ?
    """
    params = [data["name"], data["age"]]

    if exclude_id is not None:
        query += " AND id != ?"
        params.append(exclude_id)

    with connect_db() as conn:
        rows = conn.execute(query, params).fetchall()

    # A matching name and age is a warning, not proof of duplication.
    return [dict(row) for row in rows]


def save_customer(data, customer_id=None):
    now = datetime.now().isoformat(timespec="seconds")

    with connect_db() as conn:
        if customer_id is None:
            conn.execute("""
                INSERT INTO customers (
                    name, age, gender, height, weight, bmi,
                    smoking, activity, conditions, contact,
                    address, notes, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data["name"].strip(),
                data["age"],
                data["gender"],
                data["height"],
                data["weight"],
                calculate_bmi(data["height"], data["weight"]),
                data["smoking"],
                data["activity"],
                ", ".join(data["conditions"]),
                data["contact"].strip(),
                data["address"].strip(),
                data["notes"].strip(),
                now,
                now,
            ))
        else:
            conn.execute("""
                UPDATE customers
                SET name = ?, age = ?, gender = ?, height = ?,
                    weight = ?, bmi = ?, smoking = ?, activity = ?,
                    conditions = ?, contact = ?, address = ?, notes = ?,
                    updated_at = ?
                WHERE id = ? AND deleted_at IS NULL
            """, (
                data["name"].strip(),
                data["age"],
                data["gender"],
                data["height"],
                data["weight"],
                calculate_bmi(data["height"], data["weight"]),
                data["smoking"],
                data["activity"],
                ", ".join(data["conditions"]),
                data["contact"].strip(),
                data["address"].strip(),
                data["notes"].strip(),
                now,
                customer_id,
            ))


def soft_delete(customer_ids):
    if not customer_ids:
        return
    now = datetime.now().isoformat(timespec="seconds")
    with connect_db() as conn:
        conn.executemany(
            "UPDATE customers SET deleted_at = ? "
            "WHERE id = ? AND deleted_at IS NULL",
            [(now, int(cid)) for cid in customer_ids],
        )


def restore_customer(customer_id):
    with connect_db() as conn:
        conn.execute(
            "UPDATE customers SET deleted_at = NULL, updated_at = ? "
            "WHERE id = ? AND deleted_at IS NOT NULL",
            (datetime.now().isoformat(timespec="seconds"), customer_id),
        )


def permanently_delete(customer_id):
    with connect_db() as conn:
        conn.execute(
            "DELETE FROM customers WHERE id = ? AND deleted_at IS NOT NULL",
            (customer_id,),
        )


def permanently_delete_all():
    with connect_db() as conn:
        conn.execute("DELETE FROM customers WHERE deleted_at IS NOT NULL")


def dataframe_to_csv(df):
    export_df = df.copy()
    if "conditions" in export_df.columns:
        export_df["conditions"] = export_df["conditions"].fillna("")
    return export_df.to_csv(index=False).encode("utf-8-sig")


# -------------------- INITIALIZE --------------------

init_db()

st.title("🏥 Health Risk Assessment and Insurance Underwriting Platform")
st.caption("Educational mini project | Python · Streamlit · SQLite · Pandas")

with st.sidebar:
    st.title("Navigation")
    page = st.radio(
        "Choose a page",
        [
            "Dashboard",
            "New Assessment",
            "Customer Records",
            "Recently Deleted",
            "About & Disclaimer",
        ],
    )

    st.divider()
    st.caption("Demo application. Not for clinical or insurance decisions.")


# -------------------- DASHBOARD --------------------

if page == "Dashboard":
    st.header("Dashboard")
    df = fetch_customers()

    total = len(df)
    avg_bmi = float(df["bmi"].mean()) if total else 0
    high_bmi = int((df["bmi"] >= 30).sum()) if total else 0
    smokers = int((df["smoking"] == "Current").sum()) if total else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active Customers", total)
    c2.metric("Average BMI", f"{avg_bmi:.2f}" if total else "—")
    c3.metric("BMI ≥ 30", high_bmi)
    c4.metric("Current Smokers", smokers)

    st.divider()

    if total:
        left, right = st.columns(2)

        with left:
            st.subheader("BMI Distribution")
            bins = pd.cut(
                df["bmi"],
                bins=[0, 18.5, 25, 30, float("inf")],
                labels=[
                    "Below 18.5",
                    "18.5–24.9",
                    "25–29.9",
                    "30+",
                ],
                right=False,
            )
            counts = bins.value_counts(sort=False)
            st.bar_chart(counts)

        with right:
            st.subheader("Age Distribution")
            st.bar_chart(df["age"].value_counts().sort_index())

        st.subheader("Latest Customer Records")
        display_cols = [
            "id", "name", "age", "gender", "bmi",
            "smoking", "activity", "created_at",
        ]
        st.dataframe(
            df[display_cols].head(10),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No customer records yet. Open New Assessment to add your first record.")


# -------------------- NEW ASSESSMENT --------------------

elif page == "New Assessment":
    st.header("New Customer Assessment")
    st.write("Enter the details below. Fields marked * are required.")

    with st.form("new_customer_form"):
        col1, col2 = st.columns(2)

        with col1:
            name = st.text_input("Customer name *")
            age = st.number_input("Age *", min_value=1, max_value=120, value=20)
            gender = st.selectbox("Gender *", GENDERS)
            height = st.number_input(
                "Height (cm) *", min_value=50.0, max_value=250.0,
                value=170.0, step=0.5,
            )
            weight = st.number_input(
                "Weight (kg) *", min_value=2.0, max_value=500.0,
                value=65.0, step=0.5,
            )

        with col2:
            smoking = st.selectbox("Smoking status", SMOKING_OPTIONS)
            activity = st.selectbox("Physical activity", ACTIVITY_OPTIONS)
            conditions = st.multiselect("Reported health conditions", CONDITIONS)
            contact = st.text_input("Contact number")
            address = st.text_area("Address")

        notes = st.text_area("Additional notes")
        submitted = st.form_submit_button(
            "Save Assessment",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        data = {
            "name": name,
            "age": int(age),
            "gender": gender,
            "height": float(height),
            "weight": float(weight),
            "smoking": smoking,
            "activity": activity,
            "conditions": conditions,
            "contact": contact,
            "address": address,
            "notes": notes,
        }

        errors = validate_customer(data)
        if errors:
            for error in errors:
                st.error(error)
        else:
            duplicates = find_duplicate(data)
            if duplicates:
                st.warning(
                    "Possible matching customer found. Please check the records "
                    "before saving."
                )
                st.dataframe(pd.DataFrame(duplicates), hide_index=True)
                confirm_duplicate = st.checkbox(
                    "I checked the matching records and still want to save this customer."
                )
            else:
                confirm_duplicate = True

            if confirm_duplicate:
                save_customer(data)
                st.success("Customer assessment saved successfully.")
                st.info(
                    f"Calculated BMI: {calculate_bmi(data['height'], data['weight'])} "
                    f"({bmi_category(calculate_bmi(data['height'], data['weight']))})."
                )
                st.rerun()


# -------------------- CUSTOMER RECORDS --------------------

elif page == "Customer Records":
    st.header("Customer Records")
    df = fetch_customers()

    if df.empty:
        st.info("No active customer records found.")
    else:
        search = st.text_input(
            "Search by name, contact, address or customer ID",
            placeholder="Enter a search term...",
        )
        filtered = df.copy()

        if search.strip():
            term = search.strip().lower()
            mask = (
                filtered["name"].fillna("").str.lower().str.contains(term, regex=False)
                | filtered["contact"].fillna("").str.lower().str.contains(term, regex=False)
                | filtered["address"].fillna("").str.lower().str.contains(term, regex=False)
                | filtered["id"].astype(str).str.contains(term, regex=False)
            )
            filtered = filtered[mask]

        col1, col2 = st.columns(2)
        with col1:
            min_age = st.number_input(
                "Minimum age", min_value=1, max_value=120, value=1
            )
        with col2:
            max_age = st.number_input(
                "Maximum age", min_value=1, max_value=120, value=120
            )

        if min_age <= max_age:
            filtered = filtered[
                filtered["age"].between(min_age, max_age)
            ]
        else:
            st.warning("Minimum age cannot exceed maximum age.")

        st.write(f"Matching records: **{len(filtered)}**")

        visible_cols = [
            "id", "name", "age", "gender", "height", "weight", "bmi",
            "smoking", "activity", "conditions", "contact", "created_at",
        ]
        st.dataframe(
            filtered[visible_cols],
            use_container_width=True,
            hide_index=True,
        )

        st.download_button(
            "⬇️ Export filtered records to CSV",
            data=dataframe_to_csv(filtered),
            file_name="health_customer_records.csv",
            mime="text/csv",
            use_container_width=True,
        )

        st.divider()
        st.subheader("Edit Customer Details")

        ids = filtered["id"].astype(int).tolist()
        if ids:
            selected_id = st.selectbox("Select customer ID to edit", ids)
            customer = get_customer(int(selected_id))

            if customer:
                with st.form(f"edit_form_{selected_id}"):
                    ec1, ec2 = st.columns(2)

                    with ec1:
                        edit_name = st.text_input(
                            "Customer name *", value=customer["name"]
                        )
                        edit_age = st.number_input(
                            "Age *", min_value=1, max_value=120,
                            value=int(customer["age"]),
                        )
                        edit_gender = st.selectbox(
                            "Gender *", GENDERS,
                            index=GENDERS.index(customer["gender"])
                            if customer["gender"] in GENDERS else 0,
                        )
                        edit_height = st.number_input(
                            "Height (cm) *", min_value=50.0, max_value=250.0,
                            value=float(customer["height"]), step=0.5,
                        )
                        edit_weight = st.number_input(
                            "Weight (kg) *", min_value=2.0, max_value=500.0,
                            value=float(customer["weight"]), step=0.5,
                        )

                    with ec2:
                        edit_smoking = st.selectbox(
                            "Smoking status", SMOKING_OPTIONS,
                            index=SMOKING_OPTIONS.index(customer["smoking"])
                            if customer["smoking"] in SMOKING_OPTIONS else 0,
                        )
                        edit_activity = st.selectbox(
                            "Physical activity", ACTIVITY_OPTIONS,
                            index=ACTIVITY_OPTIONS.index(customer["activity"])
                            if customer["activity"] in ACTIVITY_OPTIONS else 0,
                        )

                        current_conditions = [
                            x.strip() for x in (customer["conditions"] or "").split(",")
                            if x.strip()
                        ]
                        edit_conditions = st.multiselect(
                            "Reported health conditions",
                            CONDITIONS,
                            default=[
                                x for x in current_conditions if x in CONDITIONS
                            ],
                        )
                        edit_contact = st.text_input(
                            "Contact number", value=customer["contact"] or ""
                        )
                        edit_address = st.text_area(
                            "Address", value=customer["address"] or ""
                        )

                    edit_notes = st.text_area(
                        "Additional notes", value=customer["notes"] or ""
                    )

                    update_clicked = st.form_submit_button(
                        "Save All Changes",
                        type="primary",
                        use_container_width=True,
                    )

                if update_clicked:
                    updated = {
                        "name": edit_name,
                        "age": int(edit_age),
                        "gender": edit_gender,
                        "height": float(edit_height),
                        "weight": float(edit_weight),
                        "smoking": edit_smoking,
                        "activity": edit_activity,
                        "conditions": edit_conditions,
                        "contact": edit_contact,
                        "address": edit_address,
                        "notes": edit_notes,
                    }
                    errors = validate_customer(updated)
                    duplicates = find_duplicate(updated, exclude_id=int(selected_id))

                    if errors:
                        for error in errors:
                            st.error(error)
                    elif duplicates:
                        st.warning(
                            "Another active record has the same name and age. "
                            "Please review before updating."
                        )
                        st.dataframe(pd.DataFrame(duplicates), hide_index=True)
                        force_update = st.checkbox(
                            "I checked the possible duplicate and want to save these changes.",
                            key=f"force_update_{selected_id}",
                        )
                        if force_update:
                            save_customer(updated, customer_id=int(selected_id))
                            st.success("Customer details updated.")
                            st.rerun()
                    else:
                        save_customer(updated, customer_id=int(selected_id))
                        st.success("Customer details updated.")
                        st.rerun()

        st.divider()
        st.subheader("Move Records to Recently Deleted")

        delete_ids = st.multiselect(
            "Choose customer IDs to delete",
            options=filtered["id"].astype(int).tolist(),
            format_func=lambda x: f"ID {x} — {get_customer(x)['name']}",
        )

        if st.button("Move Selected Records to Recently Deleted"):
            if delete_ids:
                soft_delete(delete_ids)
                st.success(f"{len(delete_ids)} record(s) moved to Recently Deleted.")
                st.rerun()
            else:
                st.warning("Select at least one customer.")

        st.warning("Bulk delete moves all active records to Recently Deleted; it does not permanently delete them.")
        if st.button("Move ALL Active Records to Recently Deleted"):
            st.session_state["confirm_delete_all"] = True

        if st.session_state.get("confirm_delete_all", False):
            st.error("Are you sure you want to move every active record to Recently Deleted?")
            yes_col, no_col = st.columns(2)
            with yes_col:
                if st.button("Yes, move all records"):
                    soft_delete(df["id"].astype(int).tolist())
                    st.session_state["confirm_delete_all"] = False
                    st.success("All active records moved to Recently Deleted.")
                    st.rerun()
            with no_col:
                if st.button("Cancel bulk delete"):
                    st.session_state["confirm_delete_all"] = False
                    st.rerun()


# -------------------- RECENTLY DELETED --------------------

elif page == "Recently Deleted":
    st.header("🗑️ Recently Deleted")
    st.write(
        "Deleted records are stored here until restored or permanently deleted."
    )

    all_df = fetch_customers(include_deleted=True)
    trash = all_df[all_df["deleted_at"].notna()].copy() if not all_df.empty else pd.DataFrame()

    if trash.empty:
        st.info("Recently Deleted is empty.")
    else:
        st.dataframe(
            trash[
                ["id", "name", "age", "contact", "created_at", "deleted_at"]
            ],
            use_container_width=True,
            hide_index=True,
        )

        trash_ids = trash["id"].astype(int).tolist()
        selected_trash_id = st.selectbox(
            "Select a deleted customer",
            trash_ids,
            format_func=lambda x: f"ID {x} — {get_customer(x)['name']}",
        )

        restore_col, delete_col = st.columns(2)

        with restore_col:
            if st.button("♻️ Restore Selected Customer", use_container_width=True):
                restore_customer(int(selected_trash_id))
                st.success(
                    f"Customer ID {selected_trash_id} restored with the original ID."
                )
                st.rerun()

        with delete_col:
            if st.button(
                "Permanently Delete Selected",
                type="secondary",
                use_container_width=True,
            ):
                st.session_state["confirm_permanent_id"] = int(selected_trash_id)

        permanent_id = st.session_state.get("confirm_permanent_id")
        if permanent_id is not None:
            st.error(
                f"Confirm permanent deletion of customer ID {permanent_id}. "
                "This action cannot be undone."
            )
            yes_col, no_col = st.columns(2)

            with yes_col:
                if st.button("Confirm Permanent Delete"):
                    permanently_delete(int(permanent_id))
                    st.session_state.pop("confirm_permanent_id", None)
                    st.success("Customer permanently deleted.")
                    st.rerun()

            with no_col:
                if st.button("Cancel Permanent Delete"):
                    st.session_state.pop("confirm_permanent_id", None)
                    st.rerun()

        st.divider()
        st.subheader("Permanently Delete All Records in Recently Deleted")
        st.warning("This cannot be undone.")
        if st.button("Prepare to Permanently Delete All", type="secondary"):
            st.session_state["confirm_empty_trash"] = True

        if st.session_state.get("confirm_empty_trash", False):
            st.error("Are you sure you want to permanently delete every item in Recently Deleted?")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Yes, permanently delete all"):
                    permanently_delete_all()
                    st.session_state["confirm_empty_trash"] = False
                    st.success("Recently Deleted has been emptied.")
                    st.rerun()
            with c2:
                if st.button("Cancel empty trash"):
                    st.session_state["confirm_empty_trash"] = False
                    st.rerun()


# -------------------- ABOUT & DISCLAIMER --------------------

elif page == "About & Disclaimer":
    st.header("About This Project")

    st.markdown("""
    **Health Risk Assessment and Insurance Underwriting Platform** is a
    student educational mini project developed using:

    - Python
    - Streamlit
    - SQLite
    - Pandas

    ### Main features

    - Customer assessment data entry
    - Automatic BMI calculation
    - Dashboard and basic visualizations
    - Search, filters, and CSV export
    - Edit customer information
    - Recently Deleted, restore, and permanent deletion
    - Persistent local SQLite storage

    ### BMI reference

    BMI is calculated as weight in kilograms divided by height in metres squared.
    The categories displayed are simplified adult reference ranges and are not
    suitable for diagnosing a medical condition.

    ### Important disclaimer

    This application is for educational demonstration only. It does not provide
    medical diagnosis, predict an individual's health outcomes, calculate
    insurance premiums, or make real insurance eligibility/underwriting decisions.
    Do not enter real patient or sensitive personal data into this demo.
    """)
