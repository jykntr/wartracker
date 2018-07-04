from setuptools import setup, find_packages

setup(
    name='wartracker',
    version='0.1',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'Click==6.7',
        'pymongo==3.6.1',
        'flake8==3.5.0',
        'pendulum==2.0.2',
        'apscheduler==3.5.1',
    ],
    entry_points={
        "console_scripts": [
            "wartracker = wartracker.wartracker:cli",
        ]
    }
)
