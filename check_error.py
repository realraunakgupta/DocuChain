import urllib.request
import urllib.error
import re

try:
    response = urllib.request.urlopen('http://127.0.0.1:5000/')
    print(response.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    html = e.read().decode('utf-8')
    try:
        match = re.search(r'<title>(.*?)</title>', html)
        if match:
            print("ERROR TITLE:", match.group(1))
            
        # extract text inside html to find the template file name easily
        text_lines = [line.strip() for line in html.split('\n') if line.strip()]
        for idx, line in enumerate(text_lines):
            if "TemplateSyntaxError" in line:
                for i in range(-5, 5):
                    if idx+i >= 0 and idx+i < len(text_lines):
                        print("Context:", text_lines[idx+i])
            if "File" in line and ".html" in line:
                    print("Found file ref:", line)
                    
    except Exception as e:
        print(e)
