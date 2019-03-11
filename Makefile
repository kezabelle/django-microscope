ROOT_DIR:=$(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))


help:
	@echo "clean-build - get rid of build artifacts & metadata"
	@echo "clean-pyc - get rid of dross files"
	@echo "clean - get rid of EVERYTHING dross"
	@echo "test - execute tests; calls clean-pyc for you"
	@echo "dist - build a distribution; calls test, clean-build and clean-pyc"
	@echo "check - check the quality of the built distribution; calls dist for you"
	@echo "release - register and upload to PyPI"
	@echo "mypy - check the .py files for typing"
	@echo "cythonize - check the compilation"

clean-build:
	rm -fr build/
	rm -fr htmlcov/
	rm -fr dist/
	rm -fr .eggs/
	rm -fr .mypy_cache/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +


clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*.c' -exec rm -f {} +
	find . -name '*.so' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

clean: clean-build clean-pyc;


test: clean-pyc
	python -B -R -tt -W ignore setup.py test

dist: test clean
	python setup.py sdist bdist_wheel

check: dist
	pip install check-manifest pyroma restview
	check-manifest
	pyroma .
	restview --long-description

release:
	@echo "INSTRUCTIONS:"
	@echo "- pip install wheel twine"
	@echo "- python setup.py sdist bdist_wheel"
	@echo "- ls dist/"
	@echo "- twine register dist/???"
	@echo "- twine upload dist/*"

mypy: clean-build clean-pyc
	mypy -m microscope
	mypy -m demo_project

cythonize: clean-build clean-pyc
	cythonize -i -3 microscope.py
	cythonize -i -3 demo_project.py

black:
	docker run -v $(ROOT_DIR):/code jbbarth/black *.py
