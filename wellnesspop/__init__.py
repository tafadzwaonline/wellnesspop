"""WellnessPop: event planning and financial forecasting for community wellness organizers.

Calculation modules in this package are independent of Streamlit. The UI lives in
``wellnesspop.ui`` and ``app.py``.
"""

from wellnesspop.schema import ENGINE_VERSION, SCHEMA_VERSION

__all__ = ["ENGINE_VERSION", "SCHEMA_VERSION"]
