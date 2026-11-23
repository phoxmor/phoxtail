`phoxtail db pull` backs up your local database before it dumps or
downloads anything from the server, and stops if it cannot. Before, a
failed backup printed "Safety backup skipped" and the pull went on to
replace your local database with no copy of it.
