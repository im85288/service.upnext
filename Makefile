export PYTHONPATH := $(CURDIR)/resources/lib/:$(CURDIR)/tests/
PYTHON := python
KODI_PYTHON_ABIS := 3.0.0 2.25.0

name = $(shell xmllint --xpath 'string(/addon/@id)' addon.xml)
version = $(shell xmllint --xpath 'string(/addon/@version)' addon.xml)
git_branch = $(shell git rev-parse --abbrev-ref HEAD)
git_hash = $(shell git rev-parse --short HEAD)
matrix = $(findstring $(shell xmllint --xpath 'string(/addon/requires/import[@addon="xbmc.python"]/@version)' addon.xml), $(word 1,$(KODI_PYTHON_ABIS)))

ifdef release
	zip_name = $(name)-$(version).zip
else
	zip_name = $(name)-$(version)-$(git_branch)-$(git_hash).zip
endif

include_files = addon.xml LICENSE README.md resources/
include_paths = $(patsubst %,$(name)/%,$(include_files))
exclude_files = \*.new \*.orig \*.pyc \*.pyo
zip_dir = $(name)/

languages = $(filter-out en_gb, $(patsubst resources/language/resource.language.%, %, $(wildcard resources/language/*)))

blue = \e[1;34m
white = \e[1;37m
reset = \e[0;39m

all: check test build
zip: build
test: check test-unit test-service test-run

check: check-tox check-pylint check-translations

check-tox:
	@printf "$(white)=$(blue) Starting sanity tox test$(reset)\n"
	$(PYTHON) -m tox -q

check-pylint:
	@printf "$(white)=$(blue) Starting sanity pylint test$(reset)\n"
	$(PYTHON) -m pylint -e useless-suppression resources/lib/ tests/

check-translations:
	@printf "$(white)=$(blue) Starting language test$(reset)\n"
	@-$(foreach lang,$(languages), \
		msgcmp resources/language/resource.language.$(lang)/strings.po resources/language/resource.language.en_gb/strings.po; \
	)

check-addon: clean
	@printf "$(white)=$(blue) Starting sanity addon tests$(reset)\n"
	kodi-addon-checker . --branch=leia

unit: test-unit
run: test-run

test-unit: clean
	@printf "$(white)=$(blue) Starting unit tests$(reset)\n"
	$(PYTHON) -m unittest discover

test-run:
	@printf "$(white)=$(blue) Run CLI$(reset)\n"
	$(PYTHON) resources/lib/script_entry.py
	@-pkill -ef '$(PYTHON) resources/lib/service_entry.py'
	$(PYTHON) resources/lib/service_entry.py &
	@sleep 10
#	$(PYTHON) tests/run.py
	@sleep 5
	@-pkill -ef -INT '$(PYTHON) resources/lib/service_entry.py'

build: clean
	@printf "$(white)=$(blue) Building new package$(reset)\n"
	@rm -f ../$(zip_name)
	cd ..; zip -r $(zip_name) $(include_paths) -x $(exclude_files)
	@printf "$(white)=$(blue) Successfully wrote package as: $(white)../$(zip_name)$(reset)"

multizip: clean
	@-$(foreach abi,$(KODI_PYTHON_ABIS), \
		printf "cd /addon/requires/import[@addon='xbmc.python']/@version\nset $(abi)\nsave\nbye\n" | xmllint --shell addon.xml; \
		matrix=$(findstring $(abi), $(word 1,$(KODI_PYTHON_ABIS))); \
		if [ $$matrix ]; then version=$(version)+matrix.1; else version=$(version); fi; \
		printf "cd /addon/@version\nset $$version\nsave\nbye\n" | xmllint --shell addon.xml; \
		make build; \
	)

codecov:
	@printf "$(white)=$(blue) Test codecov.yml syntax$(reset)\n"
	curl --data-binary @.codecov.yml https://codecov.io/validate

clean:
	@printf "$(white)=$(blue) Cleaning up$(reset)\n"
	find . -name '*.py[cod]' -type f -delete
	find . -name '__pycache__' -type d -delete
	rm -rf .pytest_cache/ .tox/
	rm -f *.log
