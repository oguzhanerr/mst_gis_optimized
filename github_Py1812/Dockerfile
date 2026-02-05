FROM python:3.10-slim

WORKDIR /app

# Copy repo into image
COPY . /app

# Install Py1812 and required libs
RUN pip install --no-cache-dir -e /app/Py1812 \
    matplotlib \
    geojson \
    psutil

CMD ["bash"]
