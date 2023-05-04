FROM archlinux:latest
RUN	 pacman -Syy

# Install python
RUN	 pacman -S --noconfirm python
RUN	 pacman -S --noconfirm python-pip

# File sharing
COPY build.py /
COPY simulation.py /



# Run openssh daemon
CMD	 ["/usr/sbin/sshd", "-D"]

# External packages
RUN python -m pip install numpy
RUN python -m pip install mfpymake
RUN python -m pip install flopy 
RUN python -m pip pip install https://github.com/pygsflow/pygsflow/zipball/develop 
RUN python -m pip install umbridge 
RUN python build.py


CMD python simulation.py
