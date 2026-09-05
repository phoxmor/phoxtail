# Kept out of urls.py so the app config can name the same default without
# importing the URLConf — which pulls in the registry before autodiscovery
# has run.
DEFAULT_INDEX_VIEW = "phoxtail.dashboard.views.dashboard_view"
