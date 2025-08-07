import http.client
import socket
import sys
import json
import argparse
from flask import Flask, request, jsonify, render_template

# Initialize Flask app
app = Flask(__name__)

# Define the lists of common admin paths for different technologies
# These lists are combined from both original Python scripts.
PHP_PATHS = [
    'admin/', 'administrator/', 'admin1/', 'admin2/', 'admin3/', 'admin4/', 'admin5/',
    'usuarios/', 'usuario/', 'moderator/', 'webadmin/', 'adminarea/', 'bb-admin/',
    'adminLogin/', 'admin_area/', 'panel-administracion/', 'instadmin/',
    'memberadmin/', 'administratorlogin/', 'adm/', 'admin/account.php',
    'admin/index.php', 'admin/login.php', 'admin/admin.php',
    'admin_area/admin.php', 'admin_area/login.php', 'siteadmin/login.php',
    'siteadmin/index.php', 'siteadmin/login.html', 'admin/account.html',
    'admin/index.html', 'admin/login.html', 'admin/admin.html',
    'admin_area/index.php', 'bb-admin/index.php', 'bb-admin/login.php',
    'bb-admin/admin.php', 'admin/home.php', 'admin_area/login.html',
    'admin_area/index.html', 'admin/controlpanel.php', 'admin.php',
    'admincp/index.asp', 'admincp/login.asp', 'admincp/index.html',
    'adminpanel.html', 'webadmin.html', 'webadmin/index.html',
    'webadmin/admin.html', 'webadmin/login.html', 'admin/admin_login.html',
    'admin_login.html', 'panel-administracion/login.html', 'admin/cp.php',
    'cp.php', 'administrator/index.php', 'administrator/login.php',
    'nsw/admin/login.php', 'webadmin/login.php', 'admin/admin_login.php',
    'admin_login.php', 'administrator/account.php', 'administrator.php',
    'admin_area/admin.html', 'pages/admin/admin-login.php',
    'admin/admin-login.php', 'admin-login.php', 'bb-admin/index.html',
    'bb-admin/login.html', 'acceso.php', 'bb-admin/admin.html',
    'admin/home.html', 'login.php', 'modelsearch/login.php', 'moderator.php',
    'moderator/login.php', 'moderator/admin.php', 'account.php',
    'pages/admin/admin-login.html', 'admin/admin-login.html',
    'admin-login.html', 'controlpanel.php', 'admincontrol.php',
    'admin/adminLogin.html', 'adminLogin.html', 'home.html',
    'rcjakar/admin/login.php', 'adminarea/index.html', 'adminarea/admin.html',
    'webadmin.php', 'webadmin/index.php', 'webadmin/admin.php',
    'admin/controlpanel.html', 'admin.html', 'admin/cp.html', 'cp.html',
    'adminpanel.php', 'moderator.html', 'administrator/index.html',
    'administrator/login.html', 'user.html', 'administrator/account.html',
    'administrator.html', 'login.html', 'modelsearch/login.html',
    'moderator/login.html', 'adminarea/login.html',
    'panel-administracion/index.html', 'panel-administracion/admin.html',
    'modelsearch/index.html', 'modelsearch/admin.html',
    'admincontrol/login.html', 'adm/index.html', 'adm.html',
    'moderator/admin.html', 'user.php', 'account.html', 'controlpanel.html',
    'admincontrol.html', 'panel-administracion/login.php', 'wp-login.php',
    'adminLogin.php', 'admin/adminLogin.php', 'home.php', 'admin.php',
    'adminarea/index.php', 'adminarea/admin.php', 'adminarea/login.php',
    'panel-administracion/index.php', 'panel-administracion/admin.php',
    'modelsearch/index.php', 'modelsearch/admin.php',
    'admincontrol/login.php', 'adm/admloginuser.php', 'admloginuser.php',
    'admin2.php', 'admin2/login.php', 'admin2/index.php', 'usuarios/login.php',
    'adm/index.php', 'adm.php', 'affiliate.php', 'adm_auth.php',
    'memberadmin.php', 'administratorlogin.php'
]

ASP_PATHS = [
    'admin/', 'administrator/', 'admin1/', 'admin2/', 'admin3/', 'admin4/', 'admin5/',
    'moderator/', 'webadmin/', 'adminarea/', 'bb-admin/', 'adminLogin/',
    'admin_area/', 'panel-administracion/', 'instadmin/', 'memberadmin/',
    'administratorlogin/', 'adm/', 'account.asp', 'admin/account.asp',
    'admin/index.asp', 'admin/login.asp', 'admin/admin.asp',
    'admin_area/admin.asp', 'admin_area/login.asp', 'admin/account.html',
    'admin/index.html', 'admin/login.html', 'admin/admin.html',
    'admin_area/admin.html', 'admin_area/login.html', 'admin_area/index.html',
    'admin_area/index.asp', 'bb-admin/index.asp', 'bb-admin/login.asp',
    'bb-admin/admin.asp', 'bb-admin/index.html', 'bb-admin/login.html',
    'bb-admin/admin.html', 'admin/home.html', 'admin/controlpanel.html',
    'admin.html', 'admin/cp.html', 'cp.html', 'administrator/index.html',
    'administrator/login.html', 'administrator/account.html',
    'administrator.html', 'login.html', 'modelsearch/login.html',
    'moderator.html', 'moderator/login.html', 'moderator/admin.html',
    'account.html', 'controlpanel.html', 'admincontrol.html',
    'admin_login.html', 'panel-administracion/login.html', 'admin/home.asp',
    'admin/controlpanel.asp', 'admin.asp', 'pages/admin/admin-login.asp',
    'admin/admin-login.asp', 'admin-login.asp', 'admin/cp.asp', 'cp.asp',
    'administrator/account.asp', 'administrator.asp', 'acceso.asp',
    'login.asp', 'modelsearch/login.asp', 'moderator.asp',
    'moderator/login.asp', 'administrator/login.asp', 'moderator/admin.asp',
    'controlpanel.asp', 'admin/account.html', 'adminpanel.html',
    'webadmin.html', 'pages/admin/admin-login.html', 'admin/admin-login.html',
    'webadmin/index.html', 'webadmin/admin.html', 'webadmin/login.html',
    'user.asp', 'user.html', 'admincp/index.asp', 'admincp/login.asp',
    'admincp/index.html', 'admin/adminLogin.html', 'adminLogin.html',
    'home.html', 'adminarea/index.html', 'adminarea/admin.html',
    'adminarea/login.html', 'panel-administracion/index.html',
    'panel-administracion/admin.html', 'modelsearch/index.html',
    'modelsearch/admin.html', 'admin/admin_login.html',
    'admincontrol/login.html', 'adm/index.html', 'adm.html',
    'admincontrol.asp', 'adminpanel.asp', 'webadmin.asp',
    'webadmin/index.asp', 'webadmin/admin.asp', 'webadmin/login.asp',
    'admin/admin_login.asp', 'admin_login.asp',
    'panel-administracion/login.asp', 'adminLogin.asp',
    'admin/adminLogin.asp', 'home.asp', 'admin.asp', 'adminarea/index.asp',
    'adminarea/admin.asp', 'adminarea/login.asp', 'admin-login.html',
    'panel-administracion/index.asp', 'panel-administracion/admin.asp',
    'modelsearch/index.asp', 'modelsearch/admin.asp',
    'administrator/index.asp', 'admincontrol/login.asp',
    'adm/admloginuser.asp', 'admloginuser.asp', 'admin2.asp',
    'admin2/login.asp', 'admin2/index.asp', 'adm/index.asp', 'adm.asp',
    'affiliate.asp', 'adm_auth.asp', 'memberadmin.asp', 'administratorlogin.asp',
    'siteadmin/login.asp', 'siteadmin/index.asp', 'siteadmin/login.html'
]

CFM_PATHS = [
    'admin/', 'administrator/', 'admin1/', 'admin2/', 'admin3/', 'admin4/', 'admin5/',
    'usuarios/', 'usuario/', 'administrator/', 'moderator/', 'webadmin/',
    'adminarea/', 'bb-admin/', 'adminLogin/', 'admin_area/',
    'panel-administracion/', 'instadmin/', 'memberadmin/',
    'administratorlogin/', 'adm/', 'admin/account.cfm', 'admin/index.cfm',
    'admin/login.cfm', 'admin/admin.cfm', 'admin/account.cfm',
    'admin_area/admin.cfm', 'admin_area/login.cfm', 'siteadmin/login.cfm',
    'siteadmin/index.cfm', 'siteadmin/login.html', 'admin/account.html',
    'admin/index.html', 'admin/login.html', 'admin/admin.html',
    'admin_area/index.cfm', 'bb-admin/index.cfm', 'bb-admin/login.cfm',
    'bb-admin/admin.cfm', 'admin/home.cfm', 'admin_area/login.html',
    'admin_area/index.html', 'admin/controlpanel.cfm', 'admin.cfm',
    'admincp/index.asp', 'admincp/login.asp', 'admincp/index.html',
    'admin/account.html', 'adminpanel.html', 'webadmin.html',
    'webadmin/index.html', 'webadmin/admin.html', 'webadmin/login.html',
    'admin/admin_login.html', 'admin_login.html',
    'panel-administracion/login.html', 'admin/cp.cfm', 'cp.cfm',
    'administrator/index.cfm', 'administrator/login.cfm',
    'nsw/admin/login.cfm', 'webadmin/login.cfm', 'admin/admin_login.cfm',
    'admin_login.cfm', 'administrator/account.cfm', 'administrator.cfm',
    'admin_area/admin.html', 'pages/admin/admin-login.cfm',
    'admin/admin-login.cfm', 'admin-login.cfm', 'bb-admin/index.html',
    'bb-admin/login.html', 'bb-admin/admin.html', 'admin/home.html',
    'login.cfm', 'modelsearch/login.cfm', 'moderator.cfm',
    'moderator/login.cfm', 'moderator/admin.cfm', 'account.cfm',
    'pages/admin/admin-login.html', 'admin/admin-login.html',
    'admin-login.html', 'controlpanel.cfm', 'admincontrol.cfm',
    'admin/adminLogin.html', 'acceso.cfm', 'adminLogin.html', 'home.html',
    'rcjakar/admin/login.cfm', 'adminarea/index.html', 'adminarea/admin.html',
    'webadmin.cfm', 'webadmin/index.cfm', 'webadmin/admin.cfm',
    'admin/controlpanel.html', 'admin.html', 'admin/cp.html', 'cp.html',
    'adminpanel.cfm', 'moderator.html', 'administrator/index.html',
    'administrator/login.html', 'user.html', 'administrator/account.html',
    'administrator.html', 'login.html', 'modelsearch/login.html',
    'moderator/login.html', 'adminarea/login.html',
    'panel-administracion/index.html', 'panel-administracion/admin.html',
    'modelsearch/index.html', 'modelsearch/admin.html',
    'admincontrol/login.html', 'adm/index.html', 'adm.html',
    'moderator/admin.html', 'user.cfm', 'account.html', 'controlpanel.html',
    'admincontrol.html', 'panel-administracion/login.cfm', 'wp-login.cfm',
    'adminLogin.cfm', 'admin/adminLogin.cfm', 'home.cfm', 'admin.cfm',
    'adminarea/index.cfm', 'adminarea/admin.cfm', 'adminarea/login.cfm',
    'panel-administracion/index.cfm', 'panel-administracion/admin.cfm',
    'modelsearch/index.cfm', 'modelsearch/admin.cfm',
    'admincontrol/login.cfm', 'adm/admloginuser.cfm', 'admloginuser.cfm',
    'admin2.cfm', 'admin2/login.cfm', 'admin2/index.cfm', 'usuarios/login.cfm',
    'adm/index.cfm', 'adm.cfm', 'affiliate.cfm', 'adm_auth.cfm',
    'memberadmin.cfm', 'administratorlogin.cfm'
]

JS_PATHS = [
    'admin/', 'administrator/', 'admin1/', 'admin2/', 'admin3/', 'admin4/', 'admin5/',
    'usuarios/', 'usuario/', 'administrator/', 'moderator/', 'webadmin/',
    'adminarea/', 'bb-admin/', 'adminLogin/', 'admin_area/',
    'panel-administracion/', 'instadmin/', 'memberadmin/',
    'administratorlogin/', 'adm/', 'admin/account.js', 'admin/index.js',
    'admin/login.js', 'admin/admin.js', 'admin/account.js',
    'admin_area/admin.js', 'admin_area/login.js', 'siteadmin/login.js',
    'siteadmin/index.js', 'siteadmin/login.html', 'admin/account.html',
    'admin/index.html', 'admin/login.html', 'admin/admin.html',
    'admin_area/index.js', 'bb-admin/index.js', 'bb-admin/login.js',
    'bb-admin/admin.js', 'admin/home.js', 'admin_area/login.html',
    'admin_area/index.html', 'admin/controlpanel.js', 'admin.js',
    'admincp/index.asp', 'admincp/login.asp', 'admincp/index.html',
    'admin/account.html', 'adminpanel.html', 'webadmin.html',
    'webadmin/index.html', 'webadmin/admin.html', 'webadmin/login.html',
    'admin/admin_login.html', 'admin_login.html',
    'panel-administracion/login.html', 'admin/cp.js', 'cp.js',
    'administrator/index.js', 'administrator/login.js', 'nsw/admin/login.js',
    'webadmin/login.js', 'admin/admin_login.js', 'admin_login.js',
    'administrator/account.js', 'administrator.js', 'admin_area/admin.html',
    'pages/admin/admin-login.js', 'admin/admin-login.js', 'admin-login.js',
    'bb-admin/index.html', 'bb-admin/login.html', 'bb-admin/admin.html',
    'admin/home.html', 'login.js', 'modelsearch/login.js', 'moderator.js',
    'moderator/login.js', 'moderator/admin.js', 'account.js',
    'pages/admin/admin-login.html', 'admin/admin-login.html',
    'admin-login.html', 'controlpanel.js', 'admincontrol.js',
    'admin/adminLogin.html', 'adminLogin.html', 'home.html',
    'rcjakar/admin/login.js', 'adminarea/index.html', 'adminarea/admin.html',
    'webadmin.js', 'webadmin/index.js', 'acceso.js', 'webadmin/admin.js',
    'admin/controlpanel.html', 'admin.html', 'admin/cp.html', 'cp.html',
    'adminpanel.js', 'moderator.html', 'administrator/index.html',
    'administrator/login.html', 'user.html', 'administrator/account.html',
    'administrator.html', 'login.html', 'modelsearch/login.html',
    'moderator/login.html', 'adminarea/login.html',
    'panel-administracion/index.html', 'panel-administracion/admin.html',
    'modelsearch/index.html', 'modelsearch/admin.html',
    'admincontrol/login.html', 'adm/index.html', 'adm.html',
    'moderator/admin.html', 'user.js', 'account.html', 'controlpanel.html',
    'admincontrol.html', 'panel-administracion/login.js', 'wp-login.js',
    'adminLogin.js', 'admin/adminLogin.js', 'home.js', 'admin.js',
    'adminarea/index.js', 'adminarea/admin.js', 'adminarea/login.js',
    'panel-administracion/index.js', 'panel-administracion/admin.js',
    'modelsearch/index.js', 'modelsearch/admin.js',
    'admincontrol/login.js', 'adm/admloginuser.js', 'admloginuser.js',
    'admin2.js', 'admin2/login.js', 'admin2/index.js', 'usuarios/login.js',
    'adm/index.js', 'adm.js', 'affiliate.js', 'adm_auth.js',
    'memberadmin.js', 'administratorlogin.js'
]

CGI_PATHS = [
    'admin/', 'administrator/', 'admin1/', 'admin2/', 'admin3/', 'admin4/', 'admin5/',
    'usuarios/', 'usuario/', 'administrator/', 'moderator/', 'webadmin/',
    'adminarea/', 'bb-admin/', 'adminLogin/', 'admin_area/',
    'panel-administracion/', 'instadmin/', 'memberadmin/',
    'administratorlogin/', 'adm/', 'admin/account.cgi', 'admin/index.cgi',
    'admin/login.cgi', 'admin/admin.cgi', 'admin/account.cgi',
    'admin_area/admin.cgi', 'admin_area/login.cgi', 'siteadmin/login.cgi',
    'siteadmin/index.cgi', 'siteadmin/login.html', 'admin/account.html',
    'admin/index.html', 'admin/login.html', 'admin/admin.html',
    'admin_area/index.cgi', 'bb-admin/index.cgi', 'bb-admin/login.cgi',
    'bb-admin/admin.cgi', 'admin/home.cgi', 'admin_area/login.html',
    'admin_area/index.html', 'admin/controlpanel.cgi', 'admin.cgi',
    'admincp/index.asp', 'admincp/login.asp', 'admincp/index.html',
    'admin/account.html', 'adminpanel.html', 'webadmin.html',
    'webadmin/index.html', 'webadmin/admin.html', 'webadmin/login.html',
    'admin/admin_login.html', 'admin_login.html',
    'panel-administracion/login.html', 'admin/cp.cgi', 'cp.cgi',
    'administrator/index.cgi', 'administrator/login.cgi',
    'nsw/admin/login.cgi', 'webadmin/login.cgi', 'admin/admin_login.cgi',
    'admin_login.cgi', 'administrator/account.cgi', 'administrator.cgi',
    'admin_area/admin.html', 'pages/admin/admin-login.cgi',
    'admin/admin-login.cgi', 'admin-login.cgi', 'bb-admin/index.html',
    'bb-admin/login.html', 'bb-admin/admin.html', 'admin/home.html',
    'login.cgi', 'modelsearch/login.cgi', 'moderator.cgi',
    'moderator/login.cgi', 'moderator/admin.cgi', 'account.cgi',
    'pages/admin/admin-login.html', 'admin/admin-login.html',
    'admin-login.html', 'controlpanel.cgi', 'admincontrol.cgi',
    'admin/adminLogin.html', 'adminLogin.html', 'home.html',
    'rcjakar/admin/login.cgi', 'adminarea/index.html', 'adminarea/admin.html',
    'webadmin.cgi', 'webadmin/index.cgi', 'acceso.cgi', 'webadmin/admin.cgi',
    'admin/controlpanel.html', 'admin.html', 'admin/cp.html', 'cp.html',
    'adminpanel.cgi', 'moderator.html', 'administrator/index.html',
    'administrator/login.html', 'user.html', 'administrator/account.html',
    'administrator.html', 'login.html', 'modelsearch/login.html',
    'moderator/login.html', 'adminarea/login.html',
    'panel-administracion/index.html', 'panel-administracion/admin.html',
    'modelsearch/index.html', 'modelsearch/admin.html',
    'admincontrol/login.html', 'adm/index.html', 'adm.html',
    'moderator/admin.html', 'user.cgi', 'account.html', 'controlpanel.html',
    'admincontrol.html', 'panel-administracion/login.cgi', 'wp-login.cgi',
    'adminLogin.cgi', 'admin/adminLogin.cgi', 'home.cgi', 'admin.cgi',
    'adminarea/index.cgi', 'adminarea/admin.cgi', 'adminarea/login.cgi',
    'panel-administracion/index.cgi', 'panel-administracion/admin.cgi',
    'modelsearch/index.cgi', 'modelsearch/admin.cgi',
    'admincontrol/login.cgi', 'adm/admloginuser.cgi', 'admloginuser.cgi',
    'admin2.cgi', 'admin2/login.cgi', 'admin2/index.cgi', 'usuarios/login.cgi',
    'adm/index.cgi', 'adm.cgi', 'affiliate.cgi', 'adm_auth.cgi',
    'memberadmin.cgi', 'administratorlogin.cgi'
]

BRF_PATHS = [
    'admin/', 'administrator/', 'admin1/', 'admin2/', 'admin3/', 'admin4/', 'admin5/',
    'usuarios/', 'usuario/', 'administrator/', 'moderator/', 'webadmin/',
    'adminarea/', 'bb-admin/', 'adminLogin/', 'admin_area/',
    'panel-administracion/', 'instadmin/', 'memberadmin/',
    'administratorlogin/', 'adm/', 'admin/account.brf', 'admin/index.brf',
    'admin/login.brf', 'admin/admin.brf', 'admin/account.brf',
    'admin_area/admin.brf', 'admin_area/login.brf', 'siteadmin/login.brf',
    'siteadmin/index.brf', 'siteadmin/login.html', 'admin/account.html',
    'admin/index.html', 'admin/login.html', 'admin/admin.html',
    'admin_area/index.brf', 'bb-admin/index.brf', 'bb-admin/login.brf',
    'bb-admin/admin.brf', 'admin/home.brf', 'admin_area/login.html',
    'admin_area/index.html', 'admin/controlpanel.brf', 'admin.brf',
    'admincp/index.asp', 'admincp/login.asp', 'admincp/index.html',
    'admin/account.html', 'adminpanel.html', 'webadmin.html',
    'webadmin/index.html', 'webadmin/admin.html', 'webadmin/login.html',
    'admin/admin_login.html', 'admin_login.html',
    'panel-administracion/login.html', 'admin/cp.brf', 'cp.brf',
    'administrator/index.brf', 'administrator/login.brf',
    'nsw/admin/login.brf', 'webadmin/login.brfbrf', 'admin/admin_login.brf',
    'admin_login.brf', 'administrator/account.brf', 'administrator.brf',
    'acceso.brf', 'admin_area/admin.html', 'pages/admin/admin-login.brf',
    'admin/admin-login.brf', 'admin-login.brf', 'bb-admin/index.html',
    'bb-admin/login.html', 'bb-admin/admin.html', 'admin/home.html',
    'login.brf', 'modelsearch/login.brf', 'moderator.brf',
    'moderator/login.brf', 'moderator/admin.brf', 'account.brf',
    'pages/admin/admin-login.html', 'admin/admin-login.html',
    'admin-login.html', 'controlpanel.brf', 'admincontrol.brf',
    'admin/adminLogin.html', 'adminLogin.html', 'home.html',
    'rcjakar/admin/login.brf', 'adminarea/index.html', 'adminarea/admin.html',
    'webadmin.brf', 'webadmin/index.brf', 'webadmin/admin.brf',
    'admin/controlpanel.html', 'admin.html', 'admin/cp.html', 'cp.html',
    'adminpanel.brf', 'moderator.html', 'administrator/index.html',
    'administrator/login.html', 'user.html', 'administrator/account.html',
    'administrator.html', 'login.html', 'modelsearch/login.html',
    'moderator/login.html', 'adminarea/login.html',
    'panel-administracion/index.html', 'panel-administracion/admin.html',
    'modelsearch/index.html', 'modelsearch/admin.html',
    'admincontrol/login.html', 'adm/index.html', 'adm.html',
    'moderator/admin.html', 'user.brf', 'account.html', 'controlpanel.html',
    'admincontrol.html', 'panel-administracion/login.brf', 'wp-login.brf',
    'adminLogin.brf', 'admin/adminLogin.brf', 'home.brf', 'admin.brf',
    'adminarea/index.brf', 'adminarea/admin.brf', 'adminarea/login.brf',
    'panel-administracion/index.brf', 'panel-administracion/admin.brf',
    'modelsearch/index.brf', 'modelsearch/admin.brf',
    'admincontrol/login.brf', 'adm/admloginuser.brf', 'admloginuser.brf',
    'admin2.brf', 'admin2/login.brf', 'admin2/index.brf', 'usuarios/login.brf',
    'adm/index.brf', 'adm.brf', 'affiliate.brf', 'adm_auth.brf',
    'memberadmin.brf', 'administratorlogin.brf'
]

# Mapping of code to path lists
PATH_MAP = {
    1: PHP_PATHS,
    2: ASP_PATHS,
    3: CFM_PATHS,
    4: JS_PATHS,
    5: CGI_PATHS,
    6: BRF_PATHS,
}

def scan_admin_pages(site, admin_paths):
    """
    Scans the given website for admin pages using the provided list of paths.
    Returns a list of scan results.
    """
    results = []
    var1 = 0  # Counter for admin pages found
    var2 = 0  # Counter for total pages scanned

    # Remove http:// or https:// from the site string for httplib
    site_clean = site.replace("http://", "").replace("https://", "")

    try:
        # Check if the server is online
        conn = http.client.HTTPConnection(site_clean, timeout=5)
        conn.request("HEAD", "/")
        response = conn.getresponse()
        conn.close()
        results.append({"type": "info", "message": f"[$] Yes... Server is Online: {site}"})
    except (http.client.HTTPException, socket.error) as e:
        results.append({"type": "error", "message": f"[!] Error connecting to server: {e}. Server offline or invalid URL."})
        return results
    except Exception as e:
        results.append({"type": "error", "message": f"[!] An unexpected error occurred during connection check: {e}"})
        return results

    results.append({"type": "info", "message": f"[+] Scanning {site}...\n"})

    for admin_path in admin_paths:
        admin_path_clean = "/" + admin_path.strip()
        host_url = site + admin_path_clean
        results.append({"type": "checking", "message": f"[#] Checking {host_url}..."})

        try:
            connection = http.client.HTTPConnection(site_clean, timeout=10)
            connection.request("GET", admin_path_clean)
            response = connection.getresponse()
            var2 += 1

            if response.status == 200:
                var1 += 1
                results.append({"type": "found", "message": f">>> {host_url} Admin page found!"})
            elif response.status == 404:
                pass # Not found, no message needed
            elif response.status == 302:
                results.append({"type": "redirect", "message": f">>> {host_url} Possible admin page (302 - Redirect)"})
            else:
                results.append({"type": "info", "message": f"{host_url} Interesting response: {response.status}"})
            connection.close()

        except (http.client.HTTPException, socket.error) as e:
            results.append({"type": "error", "message": f"[!] Error checking {host_url}: {e}. Skipping."})
        except Exception as e:
            results.append({"type": "error", "message": f"[!] Unexpected error for {host_url}: {e}. Skipping."})

    results.append({"type": "summary", "message": "\nCompleted \n"})
    results.append({"type": "summary", "message": f"{var1} Admin pages found"})
    results.append({"type": "summary", "message": f"{var2} total pages scanned"})
    results.append({"type": "summary", "message": "[/] The Game Over; Press Enter to Exit"})

    return results

@app.route('/')
def index():
    """
    Renders the main HTML page for the Admin Page Finder.
    """
    return render_template('index.html')

@app.route('/scan', methods=['POST'])
def scan():
    """
    API endpoint to initiate the scan.
    Receives site URL and code type, performs the scan, and returns results as JSON.
    """
    data = request.get_json()
    site = data.get('site')
    code = data.get('code')

    if not site:
        return jsonify({"status": "error", "message": "Site URL not provided."}), 400
    try:
        code = int(code)
        if code not in PATH_MAP:
            return jsonify({"status": "error", "message": "Invalid code. Please select a code from 1 to 6."}), 400
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid code. Please enter a number from 1 to 6."}), 400

    selected_paths = PATH_MAP[code]
    scan_results = scan_admin_pages(site, selected_paths)
    return jsonify({"status": "success", "results": scan_results})

@app.route('/shutdown', methods=['POST'])
def shutdown():
    """
    Endpoint to gracefully shut down the Flask application.
    This is used by the PHP launcher to stop the Python app.
    """
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()
    return jsonify({"status": "success", "message": "Server shutting down..."})

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run Flask Admin Page Finder App.')
    parser.add_argument('--port', type=int, default=5000, help='Port to run the Flask app on.')
    args = parser.parse_args()

    # Run Flask app on the specified port
    app.run(host='127.0.0.1', port=args.port)
