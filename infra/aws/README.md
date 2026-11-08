# LexIA na AWS — o que cada serviço faz (e por quê)

| Serviço | Para quê | Por que importa para o cliente |
|---|---|---|
| **Amazon S3 + Object Lock (COMPLIANCE) + KMS** | Cofre de provas: snapshots oficiais (SIGBM/SNISB), versões de modelo, decisões humanas, representações aprovadas e selos da trilha de auditoria | Lei 12.334/2010: o empreendedor responde independentemente de culpa. O cofre prova o que se sabia e decidiu, com data e hash, sem possibilidade de apagar antes do prazo |
| **Amazon Bedrock (Claude)** | A IA generativa roda na conta AWS do próprio cliente | Dados não saem do ambiente da mineradora; cobrança no contrato AWS que ela já tem |
| **App Runner ou ECS/Fargate** | Hospedar o servidor (Dockerfile na raiz) com papel IAM | Sem chaves no código; escala sob demanda |

## Passo a passo
1. `aws cloudformation deploy --template-file infra/aws/template.yaml --stack-name torre360-cofre --capabilities CAPABILITY_NAMED_IAM`
2. Anexe `ServerPolicyArn` (e, se usar Bedrock, `BedrockPolicyArn`) ao papel IAM do serviço.
3. Configure no serviço: `TORRE_S3_BUCKET=<BucketName>`, `AWS_REGION=sa-east-1`, opcional `TORRE_LLM_PROVIDER=bedrock` e `TORRE_BEDROCK_MODEL=<ID do modelo Claude habilitado no console do Bedrock>`.
4. Publique a imagem (`docker build -t torre360 .`) no ECR e crie o serviço no App Runner apontando para a porta 8765.

## Como verificar
- Tela **Fontes & Governança → Cofre de provas**: modo (`s3` ou `local`), quantidade por tipo, últimos objetos com SHA-256 e retenção.
- Testes sem rede: `python -m unittest discover -s tests -p "test_aws.py"` (S3 simulado com o Stubber do boto3; Bedrock com cliente simulado).

## O que não foi feito aqui
- Nenhum recurso foi criado em conta AWS a partir deste ambiente (sem credenciais). O template e o código foram testados localmente.
- O ID do modelo no Bedrock varia por conta/região: configure explicitamente.
