from setuptools import setup, find_packages

setup(
    name="game-scraper",
    version="1.0.0",
    description="Linux app to scrape game deals, automate purchases, and manage downloads.",
    author="Exco35",
    python_requires=">=3.11",
    packages=find_packages(),
    install_requires=[
        "requests>=2.31.0",
        "beautifulsoup4>=4.12.0",
        "lxml>=4.9.0",
        "click>=8.1.0",
        "rich>=13.0.0",
        "keyring>=24.0.0",
        "platformdirs>=3.0.0",
        "tqdm>=4.65.0",
        "schedule>=1.2.0",
        "python-dotenv>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "game-scraper=game_scraper.cli:cli",
        ],
    },
    classifiers=[
        "Environment :: Console",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3.11",
    ],
)
