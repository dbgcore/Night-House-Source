from flask import Flask, render_template, Response, make_response, abort, request
from htmlmin.main import minify
from jsmin import jsmin
from functools import wraps
import re
import time
from collections import defaultdict

app = Flask(__name__)

app.config.update(
    MINIFY_HTML=True,
    REMOVE_COMMENTS=True,
    REMOVE_EMPTY_SPACE=True,
    MINIFY_JS=True,
    RATE_LIMIT=5,
    RATE_LIMIT_WINDOW=2,
    BAN_TIME=5
)

request_times = defaultdict(list)

def check_rate_limit(ip):
    now = time.time()
    window_start = now - app.config['RATE_LIMIT_WINDOW']
    
    requests_in_window = [t for t in request_times[ip] if t > window_start]
    request_times[ip] = requests_in_window
    
    if len(requests_in_window) >= app.config['RATE_LIMIT']:
        return False
    request_times[ip].append(now)
    return True

def protect_html(html_content: str) -> str:
    if not html_content:
        return html_content
    
    if app.config['MINIFY_JS']:
        def minify_script(match):
            script_content = match.group(1)
            try:
                return f'<script>{jsmin(jsmin(script_content))}</script>'
            except:
                return match.group(0)
        
        html_content = re.sub(
            r'<script[^>]*>(.*?)</script>',
            minify_script,
            html_content,
            flags=re.DOTALL
        )
    
    return minify(
        html_content,
        remove_comments=app.config['REMOVE_COMMENTS'],
        remove_empty_space=app.config['REMOVE_EMPTY_SPACE']
    )

def minify_response(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        ip = request.remote_addr
        
        if not check_rate_limit(ip):
            time.sleep(app.config['BAN_TIME'])
            abort(429)
            
        response = f(*args, **kwargs)
        
        if isinstance(response, str):
            response = make_response(response)
        
        if (app.config['MINIFY_HTML'] and 
            response.content_type == 'text/html; charset=utf-8' and
            hasattr(response, 'set_data')):
            response.set_data(protect_html(response.get_data(as_text=True)))
        return response
    return decorated_function

@app.route('/')
@minify_response
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)