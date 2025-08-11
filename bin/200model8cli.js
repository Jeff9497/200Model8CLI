#!/usr/bin/env node

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const chalk = require('chalk');

// Get the directory where this package is installed
const packageDir = path.dirname(__dirname);
const pythonSrcDir = path.join(packageDir, 'src');

// Check if Python is available
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

// Install Python dependencies if needed
async function ensurePythonDeps() {
    const pythonCmd = await checkPython();
    if (!pythonCmd) {
        console.error(chalk.red('❌ Python is required but not found. Please install Python 3.8+'));
        process.exit(1);
    }

    // Check if dependencies are installed
    const requirementsFile = path.join(packageDir, 'requirements.txt');
    if (fs.existsSync(requirementsFile)) {
        console.log(chalk.blue('🔧 Installing Python dependencies...'));
        const pip = spawn(pythonCmd, ['-m', 'pip', 'install', '-r', requirementsFile], {
            stdio: 'inherit',
            cwd: packageDir
        });
        
        return new Promise((resolve, reject) => {
            pip.on('close', (code) => {
                if (code === 0) {
                    console.log(chalk.green('✅ Python dependencies installed'));
                    resolve();
                } else {
                    console.error(chalk.red('❌ Failed to install Python dependencies'));
                    reject(new Error('Python dependency installation failed'));
                }
            });
        });
    }
}

// Main function to run the Python CLI
async function runCLI() {
    try {
        // Ensure Python dependencies are installed
        await ensurePythonDeps();

        const pythonCmd = await checkPython();
        const mainScript = path.join(pythonSrcDir, 'model8cli', 'cli.py');
        
        // Pass all arguments to the Python script
        const args = process.argv.slice(2);
        
        const pythonProcess = spawn(pythonCmd, ['-m', 'model8cli.cli', ...args], {
            stdio: 'inherit',
            cwd: pythonSrcDir,
            env: {
                ...process.env,
                PYTHONPATH: pythonSrcDir
            }
        });

        pythonProcess.on('close', (code) => {
            process.exit(code);
        });

        pythonProcess.on('error', (error) => {
            console.error(chalk.red('❌ Failed to start 200Model8CLI:'), error.message);
            console.log(chalk.yellow('💡 Make sure Python 3.8+ is installed and accessible'));
            process.exit(1);
        });

    } catch (error) {
        console.error(chalk.red('❌ Error:'), error.message);
        process.exit(1);
    }
}

// Handle process signals
process.on('SIGINT', () => {
    process.exit(0);
});

process.on('SIGTERM', () => {
    process.exit(0);
});

// Run the CLI
runCLI().catch((error) => {
    console.error(chalk.red('❌ Unexpected error:'), error);
    process.exit(1);
});
