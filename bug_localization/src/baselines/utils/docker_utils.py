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
    Use prebuilt image provided in swe dataset lite
    directory within docker container according to gemini
    / (Root of the Docker Container)
    ├── opt/
    │   └── miniconda3/        <-- The pre-installed Python/Conda environment
    │       └── envs/
    │           └── testbed/   <-- The specific Python environment with all dependencies installed
    │
    ├── testbed/               <-- 🌟 THE MOST IMPORTANT FOLDER 🌟
    │   ├── .git/              <-- The repository is already a cloned Git repo
    │   ├── setup.py           <-- Build files
    │   ├── README.md
    │   ├── {source_code}/     <-- The actual buggy code (e.g., "django/" or "sympy/")
    │   └── tests/             <-- The test suite you will run
    │
    └── dev/null               <-- The file your `tail -f` command is staring at to stay awake
    """
    instance_id = dp['text_id'] # e.g., 'sympy__sympy-20590'
    
    # swe bench lite dataset already has prebuilt docker image, so we just need to retrieve it
    image_tag = f"sweb.eval.x86_64.{instance_id}:latest"
    
    try:
        # if we already have it
        client.images.get(image_tag)
        print(f"Image {image_tag} found locally.")
    except docker.errors.ImageNotFound:
        print(f"Pulling SWE-bench image for {instance_id} ")
        # we pull it from docker registry
        client.images.pull(
            "ghcr.io/epoch-research/swe-bench.eval.x86_64", 
            tag=instance_id
        )
        
        # Tag it locally to match the SWE-bench convention
        image = client.images.get(f"ghcr.io/epoch-research/swe-bench.eval.x86_64:{instance_id}")
        image.tag(f"sweb.eval.x86_64.{instance_id}", tag="latest")

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
            name=f"this_is_a_docker_name_for_{image_tag}",
            detach=True,
            command="tail -f /dev/null",
        )
        # print"Container for {test_spec.instance_id} created: {container.id}")
        container.start()
        container.exec_run("wget https://github.com/checkstyle/checkstyle/releases/download/checkstyle-10.18.1/checkstyle-10.18.1-all.jar -O /checkstyle.jar")
        
        # create empty Checkstyle config to ignore style and ONLY check syntax
        empty_config = '<?xml version="1.0"?><!DOCTYPE module PUBLIC "-//Puppy Crawl//DTD Check Configuration 1.3//EN" "https://checkstyle.org/dtds/configuration_1_3.dtd"><module name="Checker"></module>'
        container.exec_run(f"echo '{empty_config}' > /empty_checks.xml")

        # download Ktlint 
        container.exec_run("curl -sSLO https://github.com/pinterest/ktlint/releases/download/1.2.1/ktlint")
        container.exec_run("chmod a+x ktlint && mv ktlint /usr/local/bin/")
            
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
    
   

def clean_images(container):
    """
    Clean Docker images
    """
    try:
        print(f"Cleaning up container {container}...")
        container.stop(timeout=5)
        container.remove(force=True)
    except Exception as e:
        print(f"Warning: Failed to clean up container: {str(e)}")
    # raise NotImplementedError
