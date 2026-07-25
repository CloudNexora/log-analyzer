# Documents for Log Analyzer

This application has 3 endpoints:
- http://localhost:8000/doc
- http://localhost:8000/redoc
- http://localhost:8000/openapi.json


# How to access this app

- cd /Users/saikiranbiradar/Documents/projects/log-analyzer
- source .venv/bin/activate

- Analyze a log file and generate reports directly to the 'reports/' folder
- log-analyzer analyze sample_logs/jenkins_build.log --source auto --format all --output reports/


- Open the generated visual HTML dashboard directly in your browser
- open  reports/jenkins_build_report.html