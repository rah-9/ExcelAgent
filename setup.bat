@echo off
echo Setting up Excel Automation Agent Environment...
python -m venv venv
call venv\Scripts\activate.bat
pip install -r requirements.txt
echo Setup Complete. Activate using 'venv\Scripts\activate'.
