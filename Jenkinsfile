pipeline {
    agent any

    environment {
        // ✅ Wrap the token in single or double quotes
        SNYK_TOKEN = 'bec47eb0-2503-452a-b72d-85e1944b712f'
    }

    stages {
        stage('Clone') {
            steps {
                git branch: 'main', url: 'https://github.com/Charlee123/mydemo.git'
            }
        }

        stage('SCA - Dependency Scan') {
            steps {
                echo '🔍 Running Snyk SCA (Software Composition Analysis)...'
                bat """
                    set SNYK_TOKEN=%SNYK_TOKEN%
                    snyk test --all-projects --severity-threshold=medium
                """
            }
        }

        stage('SAST - Code Scan') {
            steps {
                echo '🧠 Running Snyk SAST (Static Code Analysis)...'
                bat """
                    set SNYK_TOKEN=%SNYK_TOKEN%
                    snyk code test
                """
            }
        }

        stage('Deploy') {
            steps {
                echo '🚀 Deploy stage (optional)'
            }
        }
    }
}
