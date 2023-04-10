freeze:
	pip3 freeze > requirements.txt

server:
	python3 server.py

client:
	python3 client.py

generate:
	cd part2; \
	python3 -m grpc_tools.protoc -I=. --python_out=. --pyi_out=. --grpc_python_out=. schema.proto; \
	cd ..

A: 
	python3 server.py A

B:
	python3 server.py B

C:
	python3 server.py C