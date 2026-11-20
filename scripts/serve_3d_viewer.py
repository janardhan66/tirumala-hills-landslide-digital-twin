"""Tirumala Hills 3D Digital Twin: Local Cesium HTTP Server.

Serves the CesiumJS 3D viewer and its GLB 3D models and textures locally
with proper CORS and MIME headers on port 8088.
"""
from __future__ import annotations

import functools
import http.server
import os
import socketserver
import sys
import webbrowser
from pathlib import Path

PORT = 8088
PROJECT_ROOT = Path(__file__).resolve().parent.parent
VIEWER_DIR = PROJECT_ROOT / "viewer" / "cesium"


class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "X-Requested-With, Content-Type")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200, "OK")
        self.end_headers()

    def guess_type(self, path):
        p_str = str(path).lower()
        if p_str.endswith(".glb"):
            return "model/gltf-binary"
        if p_str.endswith(".gltf"):
            return "model/gltf+json"
        if p_str.endswith(".geojson") or p_str.endswith(".json"):
            return "application/json"
        if p_str.endswith(".js"):
            return "application/javascript"
        if p_str.endswith(".css"):
            return "text/css"
        if p_str.endswith(".png"):
            return "image/png"
        return super().guess_type(path)


def run_server(port: int = PORT, open_browser: bool = False):
    if not VIEWER_DIR.exists():
        print(f"Error: Cesium viewer directory does not exist: {VIEWER_DIR}")
        sys.exit(1)

    socketserver.TCPServer.allow_reuse_address = True
    handler_factory = functools.partial(CORSRequestHandler, directory=str(VIEWER_DIR))

    try:
        with socketserver.TCPServer(("", port), handler_factory) as httpd:
            url = f"http://localhost:{port}/index.html"
            print("=" * 65)
            print("TIRUMALA HILLS 3D CESIUM DIGITAL TWIN SERVER")
            print("=" * 65)
            print(f"Serving 3D Viewer from: {VIEWER_DIR}")
            print(f"Access URL: {url}")
            print("Press Ctrl+C to terminate.")
            print("=" * 65)

            if open_browser:
                try:
                    webbrowser.open(url)
                except Exception:
                    pass

            httpd.serve_forever()
    except OSError as e:
        if "address already in use" in str(e).lower() or getattr(e, "winerror", None) == 10048:
            print(f"Server is already running on port {port}. Access at: http://localhost:{port}/index.html")
        else:
            raise


if __name__ == "__main__":
    should_open = "--open-browser" in sys.argv
    port_arg = PORT
    for i, arg in enumerate(sys.argv):
        if arg == "--port" and i + 1 < len(sys.argv):
            port_arg = int(sys.argv[i + 1])
    run_server(port=port_arg, open_browser=should_open)
