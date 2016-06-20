# glass-cli

This package is the Command Line Interface for working with the Glass Web Management Platform. Once installed, you can run the ```glass watch``` command in your local project folder to upload files to the Glass system automatically on save. You can also run ```glass get_all``` to pull the current live files from the server, or ```glass put_all``` to upload (and override) the server copy with your local copy. (Put_all is a blunt instrument, so be careful.)


These instructions assume basic knowlege of the Terminal, and VirtualEnv Wrapper needs to be installed on your machine. If these things don't sound familiar to you, [start with the instructions at the bottom](#start-with-the-basics), and then come back here.

### 1. Make your virtualenvironment

    $> mkvirtualenv glass-sites
    $> workon glass-sites


### 2. Clone this repository.

    $> workon glass-sites
    $> cd ~/some/code/place
    $> git clone git@github.com:kellycreativetech/glass-cli.git
    $> cd glass-cli
    $> pip install -r requirements.txt
    $> pip install -e .

Go into, or make a directory for a new site

    $> cd ~/Projects/kct_clients/
    $> mkdir issackelly.com
    $> cd issackelly.com
    $> glass configure
    (glass-sites)issackelly.com:glass configure
    Could not find a .glass config folder. Would you like to make one now? [y/N]: y
    What email did you use to sign up for glass?: issac@servee.com
    What is your password for glass?: [redacted]
    ---
    Finding sites for you
       1. Issac Kelly
       2. kalicocourt
       3. Kelly Creative Tech
       4. paulconstruction
       5. one.localhost:8000
   Which which site would you like to configure in this directory?: 1
   Writing config file to .glass/config


First, pull down all of the project files from the server. This will override anything that you have not yet uploaded, so you probably don't want to use this command more than once when you start the project.

    $> glass get_all

You may also want a glass ignore file. This works just like a [.gitignore file](https://help.github.com/articles/ignoring-files/).

.git and .glass and func.* are ignored by default.

    $> nano .glass/ignore
    # This is just like a .gitignore or .git/info/exclude file
    src/junk*.css
    local_only_dir
    *.py

Make some changes to the project files on your machine, and then deploy! This will publish your changes to the site.

    $> glass put_all

Alternatively, you can deploy to the site as you are making changes. As soon as you save a file, it will be uploaded while this command is running.

    $> glass watch




###Start with the basics

If this isn't your first experience with the Terminal and you already have [VituralEnv Wrapper](https://virtualenvwrapper.readthedocs.io/en/latest/install.html) installed, proceed to **Step 1** below. If not, and you're on a mac, follow these steps. Open the Terminal. (It's in Applications/Utilities. [Here's a quick introduction to the Terminal.](http://blog.teamtreehouse.com/introduction-to-the-mac-os-x-command-line)) paste these lines, one at a time, hitting enter between each. (This applies to the rest of the instructions below.)

Install easy_install:

    $> curl https://bootstrap.pypa.io/ez_setup.py -o - | sudo python

Install pip:

    $> sudo easy_install pip

Install VirtualEnv Wrapper:

    $> pip install virtualenvwrapper

Now that VirtualEnv Wrapper is installed, you're ready to install the Glass CLI tools. [So go back to the top!](#glass-cli)
