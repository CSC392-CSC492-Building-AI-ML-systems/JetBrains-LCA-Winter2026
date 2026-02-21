import docker
import tempfile
import os
import io
import tarfile
from pathlib import Path
from docker.models.containers import Container

def build_env_images(
    dp: BaseDataSource,
    client: DockerClient,
    path_content:str,
):
    """
    Build docker image for a single data point
    """
    repo_name = dp['repo_name']
    commit_hash = dp['commit_hash']
    
    # Create a unique name for this bug's image
    safe_repo_name = repo_name.replace("/", "_")
    image_tag = f"jetbrains-lca:{safe_repo_name}-{commit_hash[:7]}"
    
    # docker file content, to be executed within a docker container
    # We might want to do git apply like what swe bench do
    dockerfile_content = f"""
    FROM python:3.9-slim

    RUN apt-get update && apt-get install -y git

    # Clone the repository into the container
    WORKDIR /app
    RUN git clone https://github.com/{repo_name}.git .

    # Travel back in time to the exact commit where the bug existed
    RUN git checkout {commit_hash}

    # Install the repository dependencies 
    # (JetBrains repos might use different installers, so we chain fallbacks)
    RUN pip install -e . || pip install -r requirements.txt || true
    """

    # build the docker image
    with tempfile.TemporaryDirectory() as tmpdir:
        dockerfile_path = os.path.join(tmpdir, "Dockerfile")
        
        with open(dockerfile_path, "w") as f:
            f.write(dockerfile_content.strip())
            
        print(f"Building Docker image: {image_tag}...")
        
        # tell docker to build the image
        client.images.build(
            path=tmpdir,
            tag=image_tag,
            rm=True
        )
        
    print("Build complete!")
    return image_tag
    

def start_container(
    client: docker.DockerClient,
    image_tag: str,
):
    """
    Builds the instance image for the given test spec and creates a container from the image.

    Args:
        client: docker client
        image_tag: a string representing an unique image
    """
    # Build corresponding instance image
    try:
        # to check image was built successfully
        client.images.get(image_tag)
    except docker.errors.ImageNotFound as e:
        raise Exception(
            f"Error occurred while getting image {image_tag}: {str(e)}"
        )

    container = None
    try:
        # Create the container
        print(f"Creating container for {image_tag}...")

        container = client.containers.create(
            image=image_tag,
            name=f"this_is_a_docker_name"
            detach=True,
            command="tail -f /dev/null",
        )
        # print"Container for {test_spec.instance_id} created: {container.id}")
        return container
    except Exception as e:
        # stop container if an error happen
        if container:
            container.remove(force=True)
        raise RuntimeError("Error creating container")

def copy_to_container(container: Container, patch_file_path: Path, container_path: Path):
    """
    copy a patch from host into the container
    """
    tar_stream = io.BytesIO()
    
    with tarfile.open(fileobj=tar_stream, mode='w') as tar:
        # 'arcname' ensures the file is named correctly when unzipped inside the container
        tar.add(patch_file_path, arcname=container_path.name)
        
    # 2. Reset the stream position to the beginning so Docker can read it
    tar_stream.seek(0)
    
    # 3. Ensure the destination folder exists inside the container
    container.exec_run(f"mkdir -p {container_path.parent}")
    
    # 4. Inject the tar stream. Docker automatically extracts it into the target folder.
    container.put_archive(str(container_path.parent), tar_stream)
    
   

def clean_images():
    """
    Clean Docker images
    """
    # TO-DOs: Implement clean_images()
    raise NotImplementedError
