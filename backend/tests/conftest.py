import os

# Use an isolated in-memory database and disable demo auto-seeding in API tests.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["RESCUEGRID_AUTO_SEED"] = "false"
