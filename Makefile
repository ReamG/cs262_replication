freeze:
	pip3 freeze > requirements.txt

server:
	python3 server.py

client:
	python3 client.py

A: 
	python3 server.py A

B:
	python3 server.py B

C:
	python3 server.py C

runner:
	python3 runner.py
