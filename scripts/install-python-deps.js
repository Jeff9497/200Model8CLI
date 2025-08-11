#!/usr/bin/env node

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const chalk = require('chalk');

async function installPythonDeps() {
    console.log(chalk.blue('🔧 Setting up 200Model8CLI...'));
    
    // Check if Python is available
    const pythonCmd = await checkPython();
    if (!pythonCmd) {
        console.error(chalk.red('❌ Python 3.8+ is required but not found.'));
        console.log(chalk.yellow('💡 Please install Python from https://python.org'));
        process.exit(1);
    }

    console.log(chalk.green(`✅ Found Python: ${pythonCmd}`));

    // Install Python dependencies
    const packageDir = path.dirname(__dirname);
    const requirementsFile = path.join(packageDir, 'requirements.txt');
    
    if (fs.existsSync(requirementsFile)) {
        console.log(chalk.blue('📦 Installing Python dependencies...'));
        
        const pip = spawn(pythonCmd, ['-m', 'pip', 'install', '-r', requirementsFile], {
            stdio: 'inherit',
            cwd: packageDir
        });
        
        pip.on('close', (code) => {
            if (code === 0) {
                console.log(chalk.green('✅ 200Model8CLI installed successfully!'));
                console.log(chalk.cyan('🚀 Try: 200model8cli --help'));
            } else {
                console.error(chalk.red('❌ Failed to install Python dependencies'));
                process.exit(1);
            }
        });
    } else {
        console.log(chalk.green('✅ 200Model8CLI ready to use!'));
    }
}

function checkPython() {
    return new Promise((resolve) => {
        const python = spawn('python', ['--version'], { stdio: 'pipe' });
        python.on('close', (code) => {
            if (code === 0) {
                resolve('python');
            } else {
                const python3 = spawn('python3', ['--version'], { stdio: 'pipe' });
                python3.on('close', (code) => {
                    resolve(code === 0 ? 'python3' : null);
                });
            }
        });
    });
}

installPythonDeps().catch(console.error);
