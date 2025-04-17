pipeline {
    agent any

    environment {
        SNYK_TOKEN = 'bec47eb0-2503-452a-b72d-85e1944b712f'
        SNYK_PATH = 'C:\Users\share\AppData\Roaming\npm\snyk.cmd'
    }

    stages {
        stage('Clone') {
            steps {
                git branch: 'main', url: 'https://github.com/Charlee123/mydemo.git'
            }
        }

        stage('SCA - Dependency Scan') {
            steps {
                echo '🔍 Running Snyk SCA...'
                bat """
                    set SNYK_TOKEN=%SNYK_TOKEN%
                    "%SNYK_PATH%" test --all-projects --severity-threshold=medium
                """
            }
        }

        stage('SAST - Code Scan') {
            steps {
                echo '🧠 Running Snyk SAST...'
                bat """
                    set SNYK_TOKEN=%SNYK_TOKEN%
                    "%SNYK_PATH%" code test
                """
            }
        }
    }
}
