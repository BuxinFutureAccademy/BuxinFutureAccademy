import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now import and create the app
from webapp import create_app

# Create the Flask app
app = create_app()

# Export the WSGI application for Vercel
# This is the critical part Vercel looks for
app = app.wsgi_app
