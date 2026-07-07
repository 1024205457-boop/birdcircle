from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.request
import urllib.parse
import json

import os

# 从环境变量读取 API 凭证，无默认值，启动时若缺失则报错
BAIDU_CLIENT_ID = os.environ.get('BAIDU_CLIENT_ID')
BAIDU_CLIENT_SECRET = os.environ.get('BAIDU_CLIENT_SECRET')
if not BAIDU_CLIENT_ID or not BAIDU_CLIENT_SECRET:
    raise RuntimeError('请设置环境变量 BAIDU_CLIENT_ID 和 BAIDU_CLIENT_SECRET')

class ProxyHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_POST(self):
        if self.path.startswith('/api/baidu/token'):
            # 获取百度 access_token（凭证仅在服务端）
            url = f'https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={BAIDU_CLIENT_ID}&client_secret={BAIDU_CLIENT_SECRET}'
            req = urllib.request.Request(url, method='POST', data=b'')
            with urllib.request.urlopen(req) as resp:
                data = resp.read()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(data)

        elif self.path.startswith('/api/baidu/animal'):
            # 转发动物识别请求
            content_len = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_len)
            # 从 query string 获取 token
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            token = params.get('access_token', [''])[0]
            url = f'https://aip.baidubce.com/rest/2.0/image-classify/v1/animal?access_token={token}'
            req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/x-www-form-urlencoded'})
            with urllib.request.urlopen(req) as resp:
                data = resp.read()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(data)

        elif self.path.startswith('/api/zoology/'):
            # 转发中科院 API
            content_len = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_len) if content_len else b''
            # 路径映射: /api/zoology/descriptionType?xxx -> http://zoology.especies.cn/api/v1/descriptionType?xxx
            parsed = urllib.parse.urlparse(self.path)
            endpoint = parsed.path.replace('/api/zoology/', '')
            url = f'http://zoology.especies.cn/api/v1/{endpoint}?{parsed.query}'
            req = urllib.request.Request(url, method='POST', data=body)
            with urllib.request.urlopen(req) as resp:
                data = resp.read()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(data)

        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path.startswith('/api/weather/'):
            # 转发天气请求到 wttr.in
            coords = self.path.replace('/api/weather/', '')
            url = f'https://wttr.in/{coords}?format=j1'
            req = urllib.request.Request(url, headers={'User-Agent': 'curl/7.0'})
            try:
                with urllib.request.urlopen(req) as resp:
                    data = resp.read()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(data)
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b'{"error":"weather fetch failed"}')
        else:
            # 静态文件服务
            super().do_GET()

print("🐦 BirdCircle 本地服务启动: http://localhost:8000")
HTTPServer(('0.0.0.0', 8000), ProxyHandler).serve_forever()
