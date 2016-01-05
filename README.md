# glass-cli

Assumes virtualenv wrapper...

Make the new site in Glass http://glass.servee.com/sites/new

Make your virtualenvironment 

    $> mkvirtualenv glass-sites
    $> workon glass-sites
    
    
Clone this repository.

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


Probably a good idea to make sure you're in sync...

    $> glass get_all
    
You may also want a glass ignore file...

.git and .glass and func.* are ignored by default.

    $> nano .glass/ignore
    # This is just like a .gitignore or .git/info/exclude file
    src/junk*.css
    local_only_dir
    *.py

Make some changes... and then deploy!

    $> glass put_all
    
Or deploy as you're making changes cowgirl!

    $> glass watch
    
