from os import path

import pytest
import yaml


@pytest.fixture(scope="module")
def generated_config():
    return open(f"{_fixture_dir()}/generated_config.conf").read()


@pytest.fixture(scope="module")
def running_config():
    return open(f"{_fixture_dir()}/running_config.conf").read()


@pytest.fixture(scope="module")
def options_ios():
    return yaml.safe_load(open(f"{_fixture_dir()}/options_ios.yml").read())


@pytest.fixture(scope="module")
def tags_ios():
    return yaml.safe_load(open(f"{_fixture_dir()}/tags_ios.yml").read())


@pytest.fixture(scope="module")
def options_negate_with_undo():
    return yaml.safe_load(open(f"{_fixture_dir()}/options_negate_with_undo.yml").read())


def _fixture_dir():
    return path.join(path.dirname(path.realpath(__file__)), "fixtures")
