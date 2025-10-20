from setuptools import setup, find_packages
import re
import ast

with open("requirements.txt") as f:
	requirements = f.read().strip().split("\n")

_version_re = re.compile(r"__version__\s+=\s+(.*)")

with open("rnd_warehouse_management/__version__.py", "rb") as f:
	version = str(ast.literal_eval(_version_re.search(f.read().decode("utf-8")).group(1)))

setup(
	name="rnd_warehouse_management",
	version=version,
	description="RND Warehouse Management System for ERPNext with SAP-style workflow integration",
	author="MiniMax Agent",
	author_email="support@minimax.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=requirements
)
