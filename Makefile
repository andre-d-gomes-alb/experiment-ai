NAMESPACE=experiment-ai
SECRETS_FILE=./secrets.yaml
DATA ?= false

.PHONY: deploy clean test

deploy:
	helmfile apply

test:
	@echo "=> Cleaning old tests..."
	@kubectl get pod  -n $(NAMESPACE) -o name | grep '^pod/timescaledb-test-' | xargs -r kubectl delete -n $(NAMESPACE)
	@kubectl get pod  -n $(NAMESPACE) -o name | grep '^pod/mlflow-test-' | xargs -r kubectl delete -n $(NAMESPACE)
	@kubectl get pod  -n $(NAMESPACE) -o name | grep '^pod/airflow-test-' | xargs -r kubectl delete -n $(NAMESPACE)
	@kubectl get pod  -n $(NAMESPACE) -o name | grep '^pod/experimentai-test-' | xargs -r kubectl delete -n $(NAMESPACE)
	@kubectl get job  -n $(NAMESPACE) -o name | grep '^job/timescaledb-test-' | xargs -r kubectl delete -n $(NAMESPACE)
	@kubectl get job  -n $(NAMESPACE) -o name | grep '^job/mlflow-test-' | xargs -r kubectl delete -n $(NAMESPACE)
	@kubectl get job  -n $(NAMESPACE) -o name | grep '^job/airflow-test-' | xargs -r kubectl delete -n $(NAMESPACE)
	@kubectl get job  -n $(NAMESPACE) -o name | grep '^job/experimentai-test-' | xargs -r kubectl delete -n $(NAMESPACE)

	@echo "=> Running Helm tests for all releases..."
	@status=0; \
	\
	helmfile -l name=timescaledb test || status=1; \
	\
	if [ $$status -eq 0 ]; then \
		helmfile -l name=mlflow test || status=1; \
	fi; \
	\
	if [ $$status -eq 0 ]; then \
		helmfile -l name=airflow test || status=1; \
	fi; \
	\
	if [ $$status -eq 0 ]; then \
		helmfile -l name=experimentai test || status=1; \
	fi; \
	\
	if [ $$status -ne 0 ]; then \
		echo "-> Some Helm tests failed."; \
	else \
		echo "-> All Helm chart tests passed!"; \
	fi;

	@echo "=> Cleaning tests..."
	@kubectl get pod  -n $(NAMESPACE) -o name | grep '^pod/timescaledb-test-' | xargs -r kubectl delete -n $(NAMESPACE)
	@kubectl get pod  -n $(NAMESPACE) -o name | grep '^pod/mlflow-test-' | xargs -r kubectl delete -n $(NAMESPACE)
	@kubectl get pod  -n $(NAMESPACE) -o name | grep '^pod/airflow-test-' | xargs -r kubectl delete -n $(NAMESPACE)
	@kubectl get pod  -n $(NAMESPACE) -o name | grep '^pod/experimentai-test-' | xargs -r kubectl delete -n $(NAMESPACE)
	@kubectl get job  -n $(NAMESPACE) -o name | grep '^job/timescaledb-test-' | xargs -r kubectl delete -n $(NAMESPACE)
	@kubectl get job  -n $(NAMESPACE) -o name | grep '^job/mlflow-test-' | xargs -r kubectl delete -n $(NAMESPACE)
	@kubectl get job  -n $(NAMESPACE) -o name | grep '^job/airflow-test-' | xargs -r kubectl delete -n $(NAMESPACE)
	@kubectl get job  -n $(NAMESPACE) -o name | grep '^job/experimentai-test-' | xargs -r kubectl delete -n $(NAMESPACE)

	@exit $$status

clean:
	helmfile destroy
	kubectl delete -f $(SECRETS_FILE) -n $(NAMESPACE) || true
	kubectl delete namespace $(NAMESPACE) || true
ifeq ($(DATA),true)
	sudo rm -rf /mnt/data/*
endif
