from setuptools import setup, find_packages

with open("requirements.txt") as f:
	requirements = f.read().strip().split("\n")

setup(
	name="rnd_warehouse_management",
	version="1.0.0",
	description="RND Warehouse Management System for ERPNext with SAP-style workflow integration",
	author="MiniMax Agent",
	author_email="support@minimax.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=requirements
)