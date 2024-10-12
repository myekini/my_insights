# Use frappe/bench as the base image
FROM frappe/bench:latest

# Set the working directory inside the container
WORKDIR /workspace

# Copy the init.sh script from the local machine to the container
COPY init.sh /workspace/init.sh
CMD ["bash", "/workspace/init.sh"]