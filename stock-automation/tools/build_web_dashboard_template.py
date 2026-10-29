"""Generate the separate AWS mobile viewer stack; the trading stack is untouched."""
import argparse
import json
from pathlib import Path


def build():
    def ref(name): return {'Ref': name}
    def sub(text): return {'Fn::Sub': text}
    def attr(name, field='Arn'): return {'Fn::GetAtt': [name, field]}
    def trust(service): return {'Version':'2012-10-17','Statement':[{
        'Effect':'Allow','Principal':{'Service':service},'Action':'sts:AssumeRole'}]}
    table=sub('arn:${AWS::Partition}:dynamodb:${AWS::Region}:${AWS::AccountId}:table/${PaperTableName}')
    logs=sub('arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:/aws/lambda/stock-paper-web-dashboard:*')
    read_policy={'Version':'2012-10-17','Statement':[
        {'Effect':'Allow','Action':['dynamodb:Scan'],'Resource':table},
        {'Effect':'Allow','Action':['logs:CreateLogStream','logs:PutLogEvents'],'Resource':logs}]}
    resources={
      'WebBucket':{'Type':'AWS::S3::Bucket','DeletionPolicy':'Retain','UpdateReplacePolicy':'Retain','Properties':{
        'PublicAccessBlockConfiguration':{'BlockPublicAcls':True,'BlockPublicPolicy':True,
          'IgnorePublicAcls':True,'RestrictPublicBuckets':True},
        'OwnershipControls':{'Rules':[{'ObjectOwnership':'BucketOwnerEnforced'}]},
        'BucketEncryption':{'ServerSideEncryptionConfiguration':[{'ServerSideEncryptionByDefault':{'SSEAlgorithm':'AES256'}}]}}},
      'OriginAccess':{'Type':'AWS::CloudFront::OriginAccessControl','Properties':{'OriginAccessControlConfig':{
        'Name':'stock-paper-dashboard-origin','OriginAccessControlOriginType':'s3','SigningBehavior':'always','SigningProtocol':'sigv4'}}},
      'StaticCache':{'Type':'AWS::CloudFront::CachePolicy','Properties':{'CachePolicyConfig':{
        'Name':'stock-paper-dashboard-static','DefaultTTL':60,'MinTTL':0,'MaxTTL':3600,
        'ParametersInCacheKeyAndForwardedToOrigin':{'CookiesConfig':{'CookieBehavior':'none'},
          'HeadersConfig':{'HeaderBehavior':'none'},'QueryStringsConfig':{'QueryStringBehavior':'none'},
          'EnableAcceptEncodingGzip':True,'EnableAcceptEncodingBrotli':True}}}},
      'SecurityHeaders':{'Type':'AWS::CloudFront::ResponseHeadersPolicy','Properties':{'ResponseHeadersPolicyConfig':{
        'Name':'stock-paper-dashboard-security','SecurityHeadersConfig':{
          'ContentTypeOptions':{'Override':True},'FrameOptions':{'FrameOption':'DENY','Override':True},
          'ReferrerPolicy':{'ReferrerPolicy':'no-referrer','Override':True},
          'StrictTransportSecurity':{'AccessControlMaxAgeSec':31536000,'IncludeSubdomains':False,'Preload':False,'Override':True},
          'ContentSecurityPolicy':{'Override':True,'ContentSecurityPolicy':sub(
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self' https://*.execute-api.${AWS::Region}.amazonaws.com https://*.auth.${AWS::Region}.amazoncognito.com; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
            "form-action 'self' https://*.auth.${AWS::Region}.amazoncognito.com")}},
        'CustomHeadersConfig':{'Items':[{'Header':'Cache-Control','Value':'no-store','Override':True}]}}}},
      'Distribution':{'Type':'AWS::CloudFront::Distribution','Properties':{'DistributionConfig':{
        'Enabled':True,'DefaultRootObject':'index.html','Comment':'SABU authenticated paper viewer',
        'PriceClass':'PriceClass_200','HttpVersion':'http2','IPV6Enabled':True,
        'Origins':[{'Id':'private-static','DomainName':attr('WebBucket','RegionalDomainName'),
          'OriginAccessControlId':ref('OriginAccess'),'S3OriginConfig':{'OriginAccessIdentity':''}}],
        'DefaultCacheBehavior':{'TargetOriginId':'private-static','ViewerProtocolPolicy':'redirect-to-https',
          'AllowedMethods':['GET','HEAD'],'CachedMethods':['GET','HEAD'],'Compress':True,
          'CachePolicyId':ref('StaticCache'),'ResponseHeadersPolicyId':ref('SecurityHeaders')},
        'ViewerCertificate':{'CloudFrontDefaultCertificate':True,'MinimumProtocolVersion':'TLSv1.2_2021'}}}},
      'BucketPolicy':{'Type':'AWS::S3::BucketPolicy','Properties':{'Bucket':ref('WebBucket'),'PolicyDocument':{
        'Version':'2012-10-17','Statement':[
          {'Effect':'Allow','Principal':{'Service':'cloudfront.amazonaws.com'},'Action':'s3:GetObject',
            'Resource':sub('${WebBucket.Arn}/*'),'Condition':{'StringEquals':{
              'AWS:SourceArn':sub('arn:${AWS::Partition}:cloudfront::${AWS::AccountId}:distribution/${Distribution}')}}},
          {'Effect':'Deny','Principal':'*','Action':'s3:*','Resource':[attr('WebBucket'),sub('${WebBucket.Arn}/*')],
            'Condition':{'Bool':{'aws:SecureTransport':False}}}]}}},
      'UserPool':{'Type':'AWS::Cognito::UserPool','DeletionPolicy':'Retain','UpdateReplacePolicy':'Retain','Properties':{
        'UserPoolName':'stock-paper-dashboard','UserPoolTier':'LITE',
        'AdminCreateUserConfig':{'AllowAdminCreateUserOnly':True},'UsernameConfiguration':{'CaseSensitive':False},
        'MfaConfiguration':'OPTIONAL','EnabledMfas':['SOFTWARE_TOKEN_MFA'],
        'AccountRecoverySetting':{'RecoveryMechanisms':[{'Name':'admin_only','Priority':1}]},
        'Policies':{'PasswordPolicy':{'MinimumLength':12,'RequireLowercase':True,'RequireUppercase':True,
          'RequireNumbers':True,'RequireSymbols':True,'TemporaryPasswordValidityDays':3}}}},
      'LoginDomain':{'Type':'AWS::Cognito::UserPoolDomain','Properties':{
        'Domain':ref('LoginDomainPrefix'),'UserPoolId':ref('UserPool'),'ManagedLoginVersion':1}},
      'WebClient':{'Type':'AWS::Cognito::UserPoolClient','Properties':{'ClientName':'sabu-mobile-read-only',
        'UserPoolId':ref('UserPool'),'GenerateSecret':False,'PreventUserExistenceErrors':'ENABLED',
        'AllowedOAuthFlowsUserPoolClient':True,'AllowedOAuthFlows':['code'],'AllowedOAuthScopes':['openid'],
        'SupportedIdentityProviders':['COGNITO'],
        'CallbackURLs':[sub('https://${Distribution.DomainName}/')],
        'LogoutURLs':[sub('https://${Distribution.DomainName}/')],
        'AccessTokenValidity':5,'IdTokenValidity':5,'RefreshTokenValidity':1,
        'TokenValidityUnits':{'AccessToken':'minutes','IdToken':'minutes','RefreshToken':'days'},
        'EnableTokenRevocation':True}},
      'ReadBoundary':{'Type':'AWS::IAM::ManagedPolicy','Properties':{
        'ManagedPolicyName':'StockPaperWebReadBoundary','PolicyDocument':read_policy}},
      'ReadRole':{'Type':'AWS::IAM::Role','Properties':{'RoleName':'stock-paper-web-reader','Path':'/stock-paper/',
        'AssumeRolePolicyDocument':trust('lambda.amazonaws.com'),'PermissionsBoundary':ref('ReadBoundary'),
        'Policies':[{'PolicyName':'read-paper-ledger-only','PolicyDocument':read_policy}]}},
      'LogGroup':{'Type':'AWS::Logs::LogGroup','Properties':{'LogGroupName':'/aws/lambda/stock-paper-web-dashboard','RetentionInDays':7}},
      'ApiFunction':{'Type':'AWS::Lambda::Function','DependsOn':'LogGroup','Properties':{
        'FunctionName':'stock-paper-web-dashboard','Runtime':'python3.13','Handler':'paper_web_api.handler',
        'MemorySize':128,'Timeout':15,'ReservedConcurrentExecutions':2,'Role':attr('ReadRole'),
        'Code':{'S3Bucket':ref('ArtifactBucketName'),'S3Key':ref('ApiCodeKey')},
        'Environment':{'Variables':{'PAPER_TABLE':ref('PaperTableName'),'LIVE_ORDER_ENABLED':'0',
          'PAPER_WALLET_EPOCH':ref('PaperWalletEpoch'),'CLIENT_ID':ref('WebClient'),
          'TOKEN_ISSUER':sub('https://cognito-idp.${AWS::Region}.amazonaws.com/${UserPool}')}}}},
      'HttpApi':{'Type':'AWS::ApiGatewayV2::Api','Properties':{'Name':'stock-paper-web-read-only','ProtocolType':'HTTP',
        'CorsConfiguration':{'AllowOrigins':[sub('https://${Distribution.DomainName}')],
          'AllowMethods':['GET','OPTIONS'],'AllowHeaders':['authorization'],'MaxAge':300}}},
      'Authorizer':{'Type':'AWS::ApiGatewayV2::Authorizer','Properties':{'ApiId':ref('HttpApi'),
        'AuthorizerType':'JWT','Name':'owner-sign-in','IdentitySource':['$request.header.Authorization'],
        'JwtConfiguration':{'Audience':[ref('WebClient')],
          'Issuer':sub('https://cognito-idp.${AWS::Region}.amazonaws.com/${UserPool}')}}},
      'Integration':{'Type':'AWS::ApiGatewayV2::Integration','Properties':{'ApiId':ref('HttpApi'),
        'IntegrationType':'AWS_PROXY','IntegrationUri':attr('ApiFunction'),'PayloadFormatVersion':'2.0','TimeoutInMillis':15000}},
      'ReadRoute':{'Type':'AWS::ApiGatewayV2::Route','Properties':{'ApiId':ref('HttpApi'),'RouteKey':'GET /api/dashboard',
        'AuthorizationType':'JWT','AuthorizerId':ref('Authorizer'),'AuthorizationScopes':['openid'],
        'Target':{'Fn::Join':['/',['integrations',ref('Integration')]]}}},
      'ApiStage':{'Type':'AWS::ApiGatewayV2::Stage','DependsOn':'ReadRoute','Properties':{'ApiId':ref('HttpApi'),
        'StageName':'$default','AutoDeploy':True,'DefaultRouteSettings':{'ThrottlingBurstLimit':5,'ThrottlingRateLimit':2}}},
      'ApiPermission':{'Type':'AWS::Lambda::Permission','Properties':{'Action':'lambda:InvokeFunction',
        'FunctionName':ref('ApiFunction'),'Principal':'apigateway.amazonaws.com','SourceAccount':ref('AWS::AccountId'),
        'SourceArn':sub('arn:${AWS::Partition}:execute-api:${AWS::Region}:${AWS::AccountId}:${HttpApi}/*/GET/api/dashboard')}},
      'OperatorWebPolicy':{'Type':'AWS::IAM::ManagedPolicy','Properties':{'ManagedPolicyName':'StockPaperWebPublishAndReview',
        'Users':[ref('OperatorUserName')],'PolicyDocument':{'Version':'2012-10-17','Statement':[
          {'Effect':'Allow','Action':['cloudformation:DescribeStacks','cloudformation:DescribeStackEvents',
            'cloudformation:DescribeStackResources','cloudformation:GetTemplate'],
            'Resource':sub('arn:${AWS::Partition}:cloudformation:${AWS::Region}:${AWS::AccountId}:stack/stock-automation-paper-web/*')},
          {'Effect':'Allow','Action':['s3:PutObject','s3:GetObject'],'Resource':sub('${WebBucket.Arn}/*')},
          {'Effect':'Allow','Action':['s3:ListBucket'],'Resource':attr('WebBucket')},
          {'Effect':'Allow','Action':['cloudfront:GetDistribution','cloudfront:CreateInvalidation','cloudfront:GetInvalidation'],
            'Resource':sub('arn:${AWS::Partition}:cloudfront::${AWS::AccountId}:distribution/${Distribution}')},
          {'Effect':'Allow','Action':['lambda:GetFunction','lambda:GetFunctionConfiguration'],'Resource':attr('ApiFunction')},
          {'Effect':'Allow','Action':['logs:DescribeLogStreams','logs:GetLogEvents','logs:FilterLogEvents'],'Resource':logs},
          {'Effect':'Allow','Action':['cognito-idp:DescribeUserPool','cognito-idp:DescribeUserPoolClient'],
            'Resource':attr('UserPool')}]}}},
    }
    parameters={'ArtifactBucketName':{'Type':'String'},'ApiCodeKey':{'Type':'String','AllowedPattern':'config/web/[a-f0-9]{64}\\.zip'},
      'PaperTableName':{'Type':'String','Default':'stock-automation-paper','AllowedValues':['stock-automation-paper']},
      'LoginDomainPrefix':{'Type':'String','AllowedPattern':'sabu-paper-[a-f0-9]{12}'},
      'OperatorUserName':{'Type':'String','Default':'stock-paper-operator','AllowedValues':['stock-paper-operator']},
      # Shows only the wallets of the app stack's PaperWalletEpoch; empty keeps the original wallets.
      'PaperWalletEpoch':{'Type':'String','Default':'','AllowedPattern':'[A-Za-z0-9_-]{0,40}'}}
    return {'AWSTemplateFormatVersion':'2010-09-09','Description':'Authenticated HTTPS mobile viewer of the paper ledger; no orders or trading schedule changes',
      'Parameters':parameters,'Resources':resources,'Outputs':{
        'DashboardUrl':{'Value':sub('https://${Distribution.DomainName}/')},
        'ApiOrigin':{'Value':attr('HttpApi','ApiEndpoint')},'StaticBucketName':{'Value':ref('WebBucket')},
        'DistributionId':{'Value':ref('Distribution')},'ClientId':{'Value':ref('WebClient')},
        'UserPoolId':{'Value':ref('UserPool')},'ApiFunctionArn':{'Value':attr('ApiFunction')},
        'AuthOrigin':{'Value':sub('https://${LoginDomainPrefix}.auth.${AWS::Region}.amazoncognito.com')}}}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    output=Path(args.output)
    if output.exists():raise SystemExit('Preserve existing output; review before regeneration')
    output.write_text(json.dumps(build(),indent=2)+'\n',encoding='utf-8')
    print('READ_ONLY_WEB_TEMPLATE_READY; no AWS calls')
