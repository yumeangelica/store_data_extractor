FROM python:3.12-slim

WORKDIR /app

# Copy the dependencies file to the working directory
COPY requirements.txt /app

# Installs the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# COPY <source> <destination>
COPY . /app

# Set the command to run on container start (e.g. 'main.py')
CMD ["python", "run.py"]
