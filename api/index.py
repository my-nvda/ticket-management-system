from flask import Flask
app = Flask(__name__)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def home(path):
    return "<h1>🎉 Ticket System Serverless API Connected Successfully!</h1><p>Vercel is working cleanly.</p>"
