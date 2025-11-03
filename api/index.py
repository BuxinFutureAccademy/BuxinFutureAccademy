from webapp import create_app

# Initialize Flask app
app = create_app()

# Export the WSGI application for Vercel
handler = app.wsgi_app
