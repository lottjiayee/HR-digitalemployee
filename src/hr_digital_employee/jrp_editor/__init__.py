"""A lightweight standalone form for HR to create/edit a JRP YAML file (module-5 doc §7's "JRP
configuration UI" item) without touching YAML or the command line directly.

This is a temporary convenience tool, not Module 5 itself: no dashboard, no authentication, no
change history, no Pass/Reject action -- see ASSUMPTIONS.md. `config_builder.py` holds the
Streamlit-free, independently testable logic; `app.py` is the Streamlit UI built on top of it;
`launcher.py` is the `hr-digital-employee-jrp-editor` console-script entry point.
"""
