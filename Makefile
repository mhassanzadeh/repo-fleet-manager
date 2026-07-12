.PHONY: doctor test validate-docs

doctor:
	./scripts/rfm.sh doctor --config configs/goftaroo.example.json

test:
	PYTHONPATH=src python3 -m unittest discover -s tests

validate-docs:
	./scripts/rfm.sh docs --config configs/goftaroo.example.json validate-links
