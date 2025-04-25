pipeline {
    agent any

    tools {
        maven 'Maven 3'  // Referencing the Maven installation name from Global Tool Configuration
    }

    environment {
        SNYK_TOKEN = 'test'
        SNYK_PATH = 'C:/Users/share/AppData/Roaming/npm/snyk.cmd'
        AQUA_SCAN_IMAGE = 'aquasec/aqua-scanner' // Specify Aqua scanner image
    }

    stages {
        stage('Clone') {
            steps {
                git branch: 'main', url: 'https://github.com/Charlee123/mydemo.git'
            }
        }

        stage('SCA - Dependency Scan (pom.xml)') {
            steps {
                echo '🔍 Running Snyk SCA on pom.xml (non-blocking)...'
                bat """
                    set SNYK_TOKEN=%SNYK_TOKEN%
                    set MAVEN_HOME=%MAVEN_HOME%
                    set PATH=%MAVEN_HOME%\\bin;%PATH%
                    mvn dependency:tree -DoutputType=dot --batch-mode --non-recursive --file="pom.xml"
                    "%SNYK_PATH%" test --file=pom.xml --severity-threshold=low,medium,high,critical || exit 0
                """
            }
        }

        stage('SAST - Code Scan (non-blocking)') {
            steps {
                echo '🧠 Running Snyk SAST (non-blocking)...'
                bat """
                    set SNYK_TOKEN=%SNYK_TOKEN%
                    "%SNYK_PATH%" code test || exit 0
                """
            }
        }

        stage('Aqua Security Scan') {
            steps {
                script {
                    try {
                        echo 'Running Aqua Security Scan...'
                        // Run Aqua security scan (Windows version)
                        bat """
                            docker run --rm -v %CD%:/workspace %AQUA_SCAN_IMAGE% scan --path /workspace
                        """
                        echo 'Aqua Security Scan Successful'
                    } catch (Exception e) {
                        echo 'Aqua Security Scan Failed (but will not fail the build)'
                    } finally {
                        echo 'Aqua Security Scan Stage Completed'
                    }
                }
            }
        }
    }

    post {
        success {
            echo 'Pipeline completed successfully.'
        }
        failure {
            echo 'Pipeline failed.'
        }
    }
}
