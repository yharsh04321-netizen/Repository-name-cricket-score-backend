from flask import Flask, jsonify
import requests
from bs4 import BeautifulSoup
import re
import time

app = Flask(__name__)
