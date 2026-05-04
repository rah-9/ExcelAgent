#!/bin/bash
echo "Setting up Excel Automation Agent Environment..."
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
echo "Setup Complete. Activate using 'source venv/bin/activate'."
