APP := app/BitcoinAgent

.PHONY: tools doctor test index execution-apis-index help

help:
	@echo "make tools   — local CLI (no AWS)"
	@echo "make doctor  — what is missing for AWS / deploy"
	@echo "make test    — unit tests"
	@echo "make index   — rebuild rpc_index.json from this tree"
	@echo "make execution-apis-index — refresh bundled ethereum/execution-apis OpenRPC index"

tools:
	python3 $(APP)/local_cli.py

doctor:
	./scripts/doctor.sh

test:
	cd $(APP) && python3 -m unittest discover -s tests

index:
	cd $(APP) && python3 generate_rpc_index.py

execution-apis-index:
	cd $(APP) && python3 generate_execution_apis_index.py
