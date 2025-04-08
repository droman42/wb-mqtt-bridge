"""
Setup script for the wb-mqtt-bridge package.
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="wb-mqtt-bridge",
    version="0.1.0",
    author="Dmitri Romanovskij",
    author_email="dmitri.romanovski@gmail.com",
    description="A Python-based web service that acts as an MQTT client to manage multiple devices using a plugin-based architecture",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/droman42/wb-mqtt-bridge",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Home Automation",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    install_requires=[
        "fastapi>=0.68.0",
        "uvicorn>=0.15.0",
        "asyncio-mqtt>=0.10.0",
        "pydantic>=1.8.0",
        "python-dotenv>=0.19.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-cov>=2.0",
            "black>=21.0",
            "mypy>=0.9",
            "flake8>=3.9",
        ],
    },
    entry_points={
        "console_scripts": [
            "wb-mqtt-bridge=app.main:main",
        ],
    },
) 